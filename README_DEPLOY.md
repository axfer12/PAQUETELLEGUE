# PAQUETELLEGUE WEB - Guia de Despliegue en Railway

## Paso 1: Crear cuenta en Railway
1. Ve a **railway.app** y registrate con GitHub (gratis)

## Paso 2: Subir el proyecto a GitHub
1. Crea cuenta en github.com (si no tienes)
2. Crea repositorio privado llamado `paquetellegue`
3. Sube todos estos archivos al repositorio

## Paso 3: Desplegar en Railway
1. En railway.app → New Project → Deploy from GitHub
2. Selecciona tu repositorio `paquetellegue`
3. Railway detecta automaticamente Python + Procfile
4. Da clic en Deploy

## Paso 4: Variable de entorno
En Railway → tu proyecto → Variables → agregar:
```
SECRET_KEY = (cualquier string largo y aleatorio)
```

## Paso 5: Dominio personalizado (opcional)
En Railway → Settings → Domains → agregar tu dominio de GoDaddy

## Credenciales por defecto
- Usuario: admin
- Contrasena: admin123
(Cambiarla desde Admin → Usuarios)

## Estructura del proyecto
```
paquetellegue/
├── wsgi.py              # Punto de entrada
├── config.py            # Configuracion
├── requirements.txt     # Dependencias
├── Procfile             # Comando Railway
├── runtime.txt          # Version Python
└── app/
    ├── __init__.py      # App factory
    ├── models.py        # Modelo usuario
    ├── modules/         # Logica de negocio
    │   ├── api_proveedor.py  # Skydropx PRO
    │   ├── database.py       # SQLite
    │   ├── cp_lookup.py      # Autocompletado CP
    │   └── recibo_pago.py    # PDF recibos
    ├── routes/          # Endpoints
    │   ├── auth.py      # Login/logout
    │   ├── guias.py     # Paginas guias
    │   ├── api.py       # API JSON
    │   └── admin.py     # Panel admin
    ├── templates/       # HTML
    └── static/          # CSS / JS
```
