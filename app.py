from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from MySQLdb.cursors import DictCursor
import math
from urllib.parse import urlparse, urljoin

app = Flask(__name__)
app.secret_key = 'appsecretkey'

# Configuración MySQL
app.config['MYSQL_HOST'] = 'YordanickzSirias.mysql.pythonanywhere-services.com'
app.config['MYSQL_USER'] = 'YordanickzSirias'
app.config['MYSQL_PASSWORD'] = 'GymRats2025'
app.config['MYSQL_DB'] = 'YordanickzSirias$default'
app.config['MYSQL_PORT'] = 3306
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

def is_safe_url(target):
    if not target:
        return False
    host_url = request.host_url
    ref_url = urlparse(host_url)
    test_url = urlparse(urljoin(host_url, target))
    return (test_url.scheme in ('http', 'https')) and (ref_url.netloc == test_url.netloc)

# ------------------- RUTAS PRINCIPALES -------------------
@app.route('/')
@app.route('/inicio')
def inicio():
    return render_template('index.html')

@app.route('/contacto')
def contacto():
    return render_template('contacto.html')

@app.route('/acerca')
def acerca():
    return render_template('acerca.html')

@app.route('/productos')
def productos():
    return redirect(url_for('listaproducto'))

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/registro')
def registro():
    return render_template('registro.html')

# rutas compatibles usadas por templates admin/baseadmin
# "Listar" en el menú debe ir a la vista de edición/paginada (editarproductos)
@app.route('/listar_productos')
def listar_productos():
    return redirect(url_for('editarproductos'))

# "Agregar" en el menú mostrará la plantilla simple de agregar/listado (listaproducto.html)
@app.route('/listar_productos_agregados')
def listar_productos_agregados():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM productos")
        productos = cursor.fetchall() or []
    finally:
        cursor.close()

    # Renderizamos la plantilla de "agregar" (form + lista simple)
    return render_template('listaproducto.html', productos=productos)

@app.route('/listar')
def listar():
    return redirect(url_for('listausuarios'))

# ------------------- USUARIOS -------------------
@app.route('/crearusuario', methods=['POST'])
def crearusuario():
    nombre = request.form.get('nombre','').strip()
    email = request.form.get('email','').strip()
    password = request.form.get('password','')
    confirm = request.form.get('confirm_password','')
    if not nombre or not email or not password:
        flash('Completa todos los campos.', 'warning')
        return redirect(url_for('registro'))
    if password != confirm:
        flash('Las contraseñas no coinciden.', 'warning')
        return redirect(url_for('registro'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM usuario WHERE email = %s",(email,))
        if cursor.fetchone():
            flash('El correo ya está registrado.','warning')
            return redirect(url_for('registro'))
        cursor.execute("INSERT INTO usuario (nombre,email,password,id_rol) VALUES (%s,%s,%s,%s)",
                       (nombre,email,password,2))
        mysql.connection.commit()
        flash('Usuario registrado correctamente.','success')
        return redirect(url_for('login'))
    finally:
        cursor.close()

@app.route('/accesologin', methods=['GET', 'POST'])
def accesologin():
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        # usar cursor dict para evitar tuplas
        cursor = mysql.connection.cursor(DictCursor)
        cursor.execute("SELECT * FROM usuario WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        if user:
            session['logueado'] = True
            session['id'] = user['id']
            session['id_rol'] = user['id_rol']
            session['nombre'] = user.get('nombre')
            if user['id_rol'] == 1:
                return redirect(url_for('admin'))
            elif user['id_rol'] == 2:
                return redirect(url_for('usuario'))
        else:
            flash('Correo o contraseña incorrectos', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

# ------------------- ADMIN -------------------
@app.route('/admin')
def admin():
    if session.get('id_rol')==1:
        return render_template('admin.html')
    flash('Acceso restringido solo para administradores.','danger')
    return redirect(url_for('login'))

@app.route('/usuario')
def usuario():
    if session.get('id_rol') == 2:
        return render_template('usuario.html')
    else:
        flash('Acceso restringido al panel de usuarios.', 'danger')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.','success')
    return redirect(url_for('login'))

# ------------------- PRODUCTOS -------------------
@app.route('/listaproducto')
def listaproducto():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM productos")
        productos = cursor.fetchall() or []
    finally:
        cursor.close()
    return render_template('listaproducto.html', productos=productos)

@app.route('/agregar_producto', methods=['POST'])
def agregar_producto():
    nombre = request.form.get('nombre')
    precio = request.form.get('precio')
    descripcion = request.form.get('descripcion')
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("INSERT INTO productos (nombre,precio,descripcion) VALUES (%s,%s,%s)",
                       (nombre,precio,descripcion))
        mysql.connection.commit()
        flash('Producto agregado correctamente.','success')
    finally:
        cursor.close()
    # volver a la pantalla de agregar/listado para ver el producto añadido
    return redirect(url_for('listar_productos_agregados'))

@app.route('/eliminar_producto/<int:id>')
def eliminar_producto(id):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("DELETE FROM productos WHERE id=%s",(id,))
        mysql.connection.commit()
        flash('Producto eliminado correctamente.','success')
    finally:
        cursor.close()
    ref = request.referrer
    if ref and is_safe_url(ref):
        return redirect(ref)
    return redirect(url_for('listar_productos_agregados'))

# Nuevo: página de edición/gestión con filtros y paginación servidor
@app.route('/editarproductos')
def editarproductos():
    # Parámetros
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    sort = request.args.get('sort', 'id_asc')
    search = request.args.get('search', '').strip()

    # Orden mapping
    order_map = {
        'id_asc': 'id ASC',
        'precio_desc': 'precio DESC',
        'precio_asc': 'precio ASC',
        'nombre_asc': 'nombre ASC',
        'nombre_desc': 'nombre DESC'
    }
    order_clause = order_map.get(sort, 'id ASC')

    params = []
    where = ''
    if search:
        where = "WHERE nombre LIKE %s"
        params.append(f"%{search}%")

    # Conteo total
    cursor = mysql.connection.cursor()
    try:
        count_sql = f"SELECT COUNT(*) as total FROM productos {where}"
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone().get('total') or 0

        total_pages = max(1, math.ceil(total_count / per_page))
        if page < 1: page = 1
        if page > total_pages: page = total_pages

        offset = (page - 1) * per_page
        sql = f"SELECT * FROM productos {where} ORDER BY {order_clause} LIMIT %s OFFSET %s"
        exec_params = params + [per_page, offset]
        cursor.execute(sql, exec_params)
        productos = cursor.fetchall() or []
    finally:
        cursor.close()

    start_item = offset + 1 if total_count > 0 else 0
    end_item = min(offset + per_page, total_count)

    per_page_options = [5, 10, 25, 50, 100]

    # Renderizamos la plantilla de edición/paginada (agregarprod.html en tu repo)
    return render_template(
        'agregarprod.html',
        productos=productos,
        per_page_options=per_page_options,
        per_page=per_page,
        sort=sort,
        search=search,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        start_item=start_item,
        end_item=end_item
    )

@app.route('/editar_producto_modal/<int:id>', methods=['POST'])
def editar_producto_modal(id):
    nombre = request.form.get('nombre')
    precio = request.form.get('precio')
    descripcion = request.form.get('descripcion')
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("UPDATE productos SET nombre=%s, precio=%s, descripcion=%s WHERE id=%s",
                       (nombre, precio, descripcion, id))
        mysql.connection.commit()
        flash('Producto editado correctamente.','success')
    finally:
        cursor.close()
    return redirect(url_for('editarproductos'))

# ------------------- USUARIOS ------------------- (admin views)
@app.route('/listausuarios')
def listausuarios():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM usuario")
        usuarios = cursor.fetchall() or []
    finally:
        cursor.close()
    return render_template('listausuarios.html', usuarios=usuarios)

@app.route('/agregar_usuario', methods=['POST'])
def agregar_usuario():
    nombre = request.form.get('nombre')
    email = request.form.get('email')
    password = request.form.get('password')
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("INSERT INTO usuario (nombre,email,password,id_rol) VALUES (%s,%s,%s,%s)",
                       (nombre,email,password,2))
        mysql.connection.commit()
        flash('Usuario agregado correctamente.','success')
    finally:
        cursor.close()
    return redirect(url_for('listausuarios'))

@app.route('/eliminar_usuario/<int:id>')
def eliminar_usuario(id):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("DELETE FROM usuario WHERE id=%s",(id,))
        mysql.connection.commit()
        flash('Usuario eliminado correctamente.','success')
    finally:
        cursor.close()
    return redirect(url_for('listausuarios'))

@app.route('/editar_usuario_modal/<int:id>', methods=['POST'])
def editar_usuario_modal(id):
    nombre = request.form.get('nombre')
    email = request.form.get('email')
    password = request.form.get('password')
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("UPDATE usuario SET nombre=%s,email=%s,password=%s WHERE id=%s",
                       (nombre,email,password,id))
        mysql.connection.commit()
        flash('Usuario editado correctamente.','success')
    finally:
        cursor.close()
    return redirect(url_for('listausuarios'))

# ------------------- PERFIL ADMIN -------------------
@app.route('/perfil_admin')
def perfil_admin():
    if session.get('id_rol')==1:
        return render_template('perfiladmin.html')
    flash('Acceso restringido solo para administradores.','danger')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=8000)
# ...existing code...