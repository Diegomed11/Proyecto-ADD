// Datos de ejemplo para la demo de MongoDB (se carga solo en el primer arranque).
// Base: apcd_demo  ·  Colección: productos
// El campo anidado "proveedor" demuestra el aplanado automático (proveedor.nombre, proveedor.pais).

db = db.getSiblingDB("apcd_demo");

db.productos.insertMany([
  { nombre: "Laptop Pro 14",   categoria: "Computo",      precio: 1299, stock: 18, ventas_mes: 42, proveedor: { nombre: "TechNova", pais: "Mexico" } },
  { nombre: "Mouse Inalambrico", categoria: "Accesorios", precio: 25,   stock: 240, ventas_mes: 310, proveedor: { nombre: "Perifex", pais: "China" } },
  { nombre: "Monitor 27 4K",   categoria: "Computo",      precio: 389,  stock: 36, ventas_mes: 58, proveedor: { nombre: "ViewMax", pais: "Corea" } },
  { nombre: "Teclado Mecanico", categoria: "Accesorios",  precio: 79,   stock: 120, ventas_mes: 95, proveedor: { nombre: "Perifex", pais: "China" } },
  { nombre: "Audifonos ANC",   categoria: "Audio",        precio: 149,  stock: 64, ventas_mes: 130, proveedor: { nombre: "SonidoMX", pais: "Mexico" } },
  { nombre: "Webcam 1080p",    categoria: "Accesorios",   precio: 45,   stock: 88, ventas_mes: 72, proveedor: { nombre: "ViewMax", pais: "Corea" } },
  { nombre: "Disco SSD 1TB",   categoria: "Almacenamiento", precio: 99, stock: 150, ventas_mes: 210, proveedor: { nombre: "DataCore", pais: "Taiwan" } },
  { nombre: "Router WiFi 6",   categoria: "Redes",        precio: 119,  stock: 52, ventas_mes: 47, proveedor: { nombre: "NetLink", pais: "China" } },
  { nombre: "Silla Ergonomica", categoria: "Mobiliario",  precio: 219,  stock: 22, ventas_mes: 19, proveedor: { nombre: "ErgoPlus", pais: "Mexico" } },
  { nombre: "Tablet 10",       categoria: "Computo",      precio: 259,  stock: 41, ventas_mes: 63, proveedor: { nombre: "TechNova", pais: "Mexico" } },
  { nombre: "Microfono USB",   categoria: "Audio",        precio: 89,   stock: 70, ventas_mes: 54, proveedor: { nombre: "SonidoMX", pais: "Mexico" } },
  { nombre: "Hub USB-C 7en1",  categoria: "Accesorios",   precio: 39,   stock: 200, ventas_mes: 180, proveedor: { nombre: "Perifex", pais: "China" } },
  { nombre: "Bocina Bluetooth", categoria: "Audio",       precio: 65,   stock: 95, ventas_mes: 140, proveedor: { nombre: "SonidoMX", pais: "Mexico" } },
  { nombre: "Disco HDD 4TB",   categoria: "Almacenamiento", precio: 109, stock: 60, ventas_mes: 38, proveedor: { nombre: "DataCore", pais: "Taiwan" } },
  { nombre: "Cargador 65W",    categoria: "Accesorios",   precio: 35,   stock: 175, ventas_mes: 220, proveedor: { nombre: "Perifex", pais: "China" } },
  { nombre: "Switch 8 puertos", categoria: "Redes",       precio: 49,   stock: 80, ventas_mes: 33, proveedor: { nombre: "NetLink", pais: "China" } },
  { nombre: "Lampara LED",     categoria: "Mobiliario",   precio: 29,   stock: 130, ventas_mes: 88, proveedor: { nombre: "ErgoPlus", pais: "Mexico" } },
  { nombre: "Laptop Air 13",   categoria: "Computo",      precio: 999,  stock: 27, ventas_mes: 51, proveedor: { nombre: "TechNova", pais: "Mexico" } },
  { nombre: "Mousepad XL",     categoria: "Accesorios",   precio: 19,   stock: 300, ventas_mes: 260, proveedor: { nombre: "Perifex", pais: "China" } },
  { nombre: "Camara Web 4K",   categoria: "Accesorios",   precio: 129,  stock: 33, ventas_mes: 41, proveedor: { nombre: "ViewMax", pais: "Corea" } }
]);

print("Sembrados " + db.productos.countDocuments() + " productos en apcd_demo.");
