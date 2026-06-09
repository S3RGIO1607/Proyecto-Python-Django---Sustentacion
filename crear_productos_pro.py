import pandas as pd
import os

folder = 'data_productos_arrons'
if not os.path.exists(folder):
    os.makedirs(folder)

productos = [
    # Mobiliario
    {'nombre': 'Silla Phoenix Cristal', 'desc': 'Silla transparente de alta resistencia', 'compra': 110000, 'alquiler': 7000, 'stock': 1000},
    {'nombre': 'Silla Crossback Madera', 'desc': 'Silla rustica para eventos campestres', 'compra': 95000, 'alquiler': 6000, 'stock': 800},
    {'nombre': 'Mesa Espejo Lujo', 'desc': 'Mesa rectangular con acabado en espejo', 'compra': 450000, 'alquiler': 50000, 'stock': 1000},
    {'nombre': 'Sala Lounge Blanca', 'desc': 'Set de 4 puffs y mesa de centro', 'compra': 600000, 'alquiler': 80000, 'stock': 500},
    {'nombre': 'Silla Rimax Blanca', 'desc': 'Silla plastica estandar', 'compra': 25000, 'alquiler': 1500, 'stock': 3000},
    {'nombre': 'Silla Tiffany Dorada', 'desc': 'Silla de lujo para bodas', 'compra': 85000, 'alquiler': 5000, 'stock': 1500},
    {'nombre': 'Meson Tablon 1.80m', 'desc': 'Mesa plegable reforzada', 'compra': 75000, 'alquiler': 10000, 'stock': 400},
    # Mantelería
    {'nombre': 'Mantel Jacquard Dorado', 'desc': 'Tela labrada de alta gala', 'compra': 45000, 'alquiler': 12000, 'stock': 250},
    {'nombre': 'Camino de Mesa Encaje', 'desc': 'Detalle vintage para mesas', 'compra': 15000, 'alquiler': 4000, 'stock': 500},
    {'nombre': 'Servilleta de Tela Lujo', 'desc': 'Pack x12 algodon egipcio', 'compra': 40000, 'alquiler': 8000, 'stock': 500},
    {'nombre': 'Faldon para Mesa Principal', 'desc': 'Plisado blanco satinado', 'compra': 35000, 'alquiler': 10000, 'stock': 600},
    # Cristalería
    {'nombre': 'Copa Champana Flauta', 'desc': 'Cristal templado pack x12', 'compra': 72000, 'alquiler': 12000, 'stock': 800},
    {'nombre': 'Copa Martini Especial', 'desc': 'Diseño clasico para coctel', 'compra': 8000, 'alquiler': 1500, 'stock': 600},
    {'nombre': 'Vaso Whisky Tallado', 'desc': 'Cristal pesado de lujo', 'compra': 9000, 'alquiler': 2000, 'stock': 700},
    {'nombre': 'Plato de Sitio Vidrio', 'desc': 'Base con borde plateado', 'compra': 18000, 'alquiler': 3500, 'stock': 400},
    {'nombre': 'Cubiertos Dorados Set', 'desc': 'Cuchara, tenedor y cuchillo de lujo', 'compra': 25000, 'alquiler': 5000, 'stock': 400},
    # Menaje y otros
    {'nombre': 'Chafing Dish Acero', 'desc': 'Samovar para comida caliente', 'compra': 180000, 'alquiler': 25000, 'stock': 300},
    {'nombre': 'Jarra de Jugo Vidrio', 'desc': 'Capacidad 2 litros', 'compra': 15000, 'alquiler': 3000, 'stock': 200},
    {'nombre': 'Bandeja de Mesero Antideslizante', 'desc': 'Fibra de vidrio profesional', 'compra': 45000, 'alquiler': 5000, 'stock': 150},
    {'nombre': 'Hielera Acero Inoxidable', 'desc': 'Capacidad 5 litros con pinza', 'compra': 35000, 'alquiler': 6000, 'stock': 100},
    {'nombre': 'Alfombra Roja 10m', 'desc': 'Camino de honor para eventos', 'compra': 200000, 'alquiler': 50000, 'stock': 30},
    {'nombre': 'Poste de Fila Dorado', 'desc': 'Separador con cordon rojo', 'compra': 120000, 'alquiler': 15000, 'stock': 20},
    {'nombre': 'Arco para Globos Metalico', 'desc': 'Estructura desarmable redonda', 'compra': 150000, 'alquiler': 30000, 'stock': 50},
    {'nombre': 'Sombrilla de Sol Gigante', 'desc': 'Para eventos al aire libre', 'compra': 180000, 'alquiler': 35000, 'stock': 80},
    {'nombre': 'Carpa 4x4 Blanca', 'desc': 'Impermeable reforzada', 'compra': 900000, 'alquiler': 120000, 'stock': 80},
]

for p in productos:
    p['imagen'] = p['nombre'].replace(" ", "_") + ".jpg"

df = pd.DataFrame(productos)
df.to_csv(f'{folder}/super_carga.csv', index=False, encoding='utf-8-sig')
print(f"✅ CSV creado con {len(productos)} productos.")