const functions = require("firebase-functions");
const admin = require("firebase-admin");

admin.initializeApp();
const db = admin.firestore();

// Firestore max 500 ops/batch; worst case 2 ops/product.
const BATCH_SIZE = 250;

/**
 * Returns true if price changed (including null/undefined).
 * @param {*} oldVal - Previous price.
 * @param {*} newVal - New price.
 * @return {boolean}
 */
function priceChanged(oldVal, newVal) {
  if (oldVal === undefined || oldVal === null) return true;
  if (newVal === undefined || newVal === null) return oldVal !== newVal;
  return Number(oldVal) !== Number(newVal);
}

/**
 * Firestore doc IDs cannot contain /. Replace to avoid invalid ID.
 * @param {*} id - Raw document ID.
 * @return {string|null} Safe ID or null.
 */
function safeDocId(id) {
  if (id == null || id === "") return null;
  const s = String(id);
  return s.includes("/") ? s.replace(/\//g, "_") : s;
}

/**
 * Coerce to number or null; Firestore rejects NaN.
 * @param {*} val - Value to convert.
 * @return {number|null} Finite number or null.
 */
function toNumber(val) {
  if (val === undefined || val === null || val === "") return null;
  const n = Number(val);
  return Number.isFinite(n) ? n : null;
}

/**
 * Build product data for Firestore (no undefined, no NaN).
 * @param {Object} p - Product from request body.
 * @return {Object} Data object for Firestore.
 */
function buildProductData(p) {
  const def = function(v, fallback) {
    return v != null ? v : fallback;
  };
  return {
    name: def(p.name, ""),
    supermarket: def(p.supermarket, ""),
    category: def(p.category, def(p.category_path, "")),
    master_category_id: def(p.master_category_id, null),
    price: toNumber(p.price),
    price_per_unit: toNumber(p.price_per_unit),
    unit: def(p.unit, null),
    brand: def(p.brand, null),
    url: def(p.url, ""),
    image_url: def(p.image_url, ""),
    last_seen: admin.firestore.FieldValue.serverTimestamp(),
  };
}

exports.ingestProducts = functions.https.onRequest(async (req, res) => {
  try {
    if (req.method !== "POST") {
      return res.status(405).send("Method Not Allowed");
    }
    const body = req.body;
    if (!body || typeof body !== "object") {
      return res.status(400).send("body must be JSON with products array");
    }
    const products = body.products;

    if (!Array.isArray(products)) {
      return res.status(400).send("products must be an array");
    }

    const validProducts = products
        .filter((p) => p && (p.id != null && p.id !== ""))
        .map((p) => ({...p, _docId: safeDocId(p.id)}))
        .filter((p) => p._docId);

    const stats = {new: 0, updated: 0, unchanged: 0};

    for (let offset = 0; offset < validProducts.length; offset += BATCH_SIZE) {
      const chunk = validProducts.slice(offset, offset + BATCH_SIZE);
      const refs = chunk.map((p) =>
        db.collection("products").doc(p._docId),
      );
      const docs = await db.getAll(...refs);
      const batch = db.batch();

      chunk.forEach((p, index) => {
        const ref = refs[index];
        const existingDoc = docs[index];
        const data = buildProductData(p);

        if (!existingDoc.exists) {
          data.created_at = admin.firestore.FieldValue.serverTimestamp();
          batch.set(ref, data);
          stats.new++;
        } else {
          const existing = existingDoc.data();
          const oldPrice = existing.price;

          if (priceChanged(oldPrice, data.price)) {
            batch.set(ref, data, {merge: true});
            const historyRef = ref
                .collection("price_history")
                .doc();
            batch.set(historyRef, {
              price: oldPrice != null ? oldPrice : null,
              changed_at: admin.firestore.FieldValue.serverTimestamp(),
            });
            stats.updated++;
          } else {
            batch.update(ref, {
              last_seen: admin.firestore.FieldValue.serverTimestamp(),
            });
            stats.unchanged++;
          }
        }
      });

      await batch.commit();
    }

    res.status(200).json({
      ok: true,
      count: validProducts.length,
      new: stats.new,
      updated: stats.updated,
      unchanged: stats.unchanged,
    });
  } catch (e) {
    console.error("ingestProducts error:", e);
    res.status(500).json({
      error: e.message || String(e),
      stack: e.stack,
    });
  }
});
