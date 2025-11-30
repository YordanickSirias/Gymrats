from flask import Flask
from flask_bcrypt import Bcrypt  # Asegúrate de tener instalado: pip install flask-bcrypt

app = Flask(__name__)
bcrypt = Bcrypt(app)  # Crea una instancia de Bcrypt pasando la app

# 1. Encriptar una contraseña
password_plana = "password123"
hash_almacenado = bcrypt.generate_password_hash(password_plana).decode('utf-8')
print(f"Contraseña encriptada: {hash_almacenado}")

# 2. Verificar contraseñas
contraseña_ingresada = "password123"
contraseña_incorrecta = "contraseña_otra"

# Comprobar si el hash coincide con la contraseña ingresada
if bcrypt.check_password_hash(hash_almacenado, contraseña_ingresada):
    print("La contraseña es correcta.")
else:
    print("La contraseña es incorrecta.")

# Comprobar si el hash coincide con una contraseña incorrecta
if bcrypt.check_password_hash(hash_almacenado, contraseña_incorrecta):
    print("La contraseña es correcta.")
else:
    print("La contraseña es incorrecta.")
