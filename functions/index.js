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

exports.ingestProducts = functions.https.onRequest(async (req, res) => {
  try {
    const products = req.body.products;

    if (!Array.isArray(products)) {
      return res.status(400).send("products must be an array");
    }

    const validProducts = products.filter((p) => p.id);
    const stats = {new: 0, updated: 0, unchanged: 0};

    for (let offset = 0; offset < validProducts.length; offset += BATCH_SIZE) {
      const chunk = validProducts.slice(offset, offset + BATCH_SIZE);
      const refs = chunk.map((p) =>
        db.collection("products").doc(String(p.id)),
      );
      const docs = await db.getAll(...refs);
      const batch = db.batch();

      chunk.forEach((p, index) => {
        const ref = refs[index];
        const existingDoc = docs[index];
        const data = {
          name: p.name,
          supermarket: p.supermarket,
          category_path: p.category_path,
          price: p.price,
          price_per_unit: p.price_per_unit,
          unit: p.unit,
          brand: p.brand || null,
          url: p.url,
          image_url: p.image_url,
          last_seen: admin.firestore.FieldValue.serverTimestamp(),
        };

        if (!existingDoc.exists) {
          data.created_at = admin.firestore.FieldValue.serverTimestamp();
          batch.set(ref, data);
          stats.new++;
        } else {
          const existing = existingDoc.data();
          const oldPrice = existing.price;

          if (priceChanged(oldPrice, p.price)) {
            batch.set(ref, data, {merge: true});
            const historyRef = ref
                .collection("price_history")
                .doc();
            batch.set(historyRef, {
              price: oldPrice,
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
    res.status(500).send(e.toString());
  }
});
