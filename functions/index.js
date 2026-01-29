const functions = require("firebase-functions");
const admin = require("firebase-admin");

admin.initializeApp();
const db = admin.firestore();

exports.ingestProducts = functions.https.onRequest(async (req, res) => {
  try {
    const products = req.body.products;

    if (!Array.isArray(products)) {
      return res.status(400).send("products must be an array");
    }

    const batch = db.batch();

    products.forEach((p) => {
      if (!p.id) return;

      const ref = db.collection("products").doc(p.id);
      batch.set(ref, {
        name: p.name,
        supermarket: p.supermarket,
        category_path: p.category_path,
        price: p.price,
        price_per_unit: p.price_per_unit,
        unit: p.unit,
        url: p.url,
        image_url: p.image_url,
        last_seen: admin.firestore.FieldValue.serverTimestamp(),
        created_at: admin.firestore.FieldValue.serverTimestamp(),
      }, {merge: true});
    });

    await batch.commit();
    res.status(200).json({ok: true, count: products.length});
  } catch (e) {
    res.status(500).send(e.toString());
  }
});
