from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from urllib.parse import urlparse, urljoin
from flask_bcrypt import Bcrypt
from datetime import date
import os
import math

try:
    from flask_mysqldb import MySQL
except Exception:
    import pymysql
    pymysql.install_as_MySQLdb()
    from flask_mysqldb import MySQL


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret')

# Configuración MySQL
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'b6rapqamasvmytew2ty1-mysql.services.clever-cloud.com')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', '3306'))
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'umutvnk2oo5arwhr')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', 'EZXQHOk9WCm8ZoNLGM95')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'b6rapqamasvmytew2ty1')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'


mysql = MySQL(app)
bcrypt = Bcrypt(app)

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
@app.route('/listar_productos')
def listar_productos():
    return redirect(url_for('editarproductos'))

@app.route('/listar_productos_agregados')
def listar_productos_agregados():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM productos")
        productos = cursor.fetchall() or []
    finally:
        cursor.close()
    return render_template('listaproducto.html', productos=productos)

@app.route('/listar')
def listar():
    return redirect(url_for('listausuarios'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logueado'):
        flash('Inicia sesión para acceder al dashboard.', 'warning')
        return redirect(url_for('login'))
    # métricas simples
    usuarios_count = 0
    productos_count = 0
    cur = mysql.connection.cursor()
    try:
        cur.execute("SELECT COUNT(*) AS c FROM usuario")
        usuarios_count = cur.fetchone()['c']
        cur.execute("SELECT COUNT(*) AS c FROM productos")
        productos_count = cur.fetchone()['c']
    finally:
        cur.close()
    return render_template('dashboard.html',
                           usuarios_count=usuarios_count,
                           productos_count=productos_count)

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
        cursor.execute("SELECT id FROM usuario WHERE email = %s",(email,))
        if cursor.fetchone():
            flash('El correo ya está registrado.','warning')
            return redirect(url_for('registro'))

        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        cursor.execute("""
            INSERT INTO usuario (nombre,email,password,id_rol,created_at,login_count,last_login)
            VALUES (%s,%s,%s,%s,NOW(),0,NULL)
        """, (nombre,email,hashed,2))
        mysql.connection.commit()
        flash('Usuario registrado correctamente.','success')
        return redirect(url_for('registro'))
    finally:
        cursor.close()

@app.route('/accesologin', methods=['GET', 'POST'])

def accesologin():
    try:
        if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
            email = request.form['email']
            password = request.form['password']

            app.logger.debug("Intento de login para email=%s", email)

            cursor = mysql.connection.cursor()
            try:
                cursor.execute("SELECT * FROM usuario WHERE email = %s", (email,))
                user = cursor.fetchone()
            finally:
                cursor.close()

            app.logger.debug("Usuario obtenido: %s", {
                'found': bool(user),
                'id': user.get('id') if user else None,
                'email': user.get('email') if user else None,
                'pwd_present': bool(user and user.get('password')),
                'pwd_len': len(user.get('password')) if user and user.get('password') else 0,
                'keys': list(user.keys()) if user else []
            })

            is_valid = False
            if user:
                try:
                    is_valid = bcrypt.check_password_hash(user['password'], password)
                except Exception as ex:
                    app.logger.exception("Error al verificar contraseña con bcrypt")
                    # fallback: comparación simple (solo para debug, migrar a hashes)
                    is_valid = (user.get('password') == password)

            if user and is_valid:
                cur2 = mysql.connection.cursor()
                try:
                    cur2.execute("UPDATE usuario SET login_count = login_count + 1, last_login = NOW() WHERE id = %s", (user['id'],))
                    mysql.connection.commit()
                finally:
                    cur2.close()

                session['logueado'] = True
                session['id'] = user['id']
                session['id_rol'] = user['id_rol']
                session['nombre'] = user.get('nombre')

                flash('Sesión iniciada correctamente.', 'success')

                if user['id_rol'] == 1:
                    return redirect(url_for('admin'))
                elif user['id_rol'] == 2:
                    return redirect(url_for('usuario'))
            else:
                flash('Correo o contraseña incorrectos', 'danger')
                return redirect(url_for('login'))
        return render_template('login.html')
    except Exception:
        app.logger.exception("Error en accesologin (capturado)")
        flash('Se produjo un error interno. Revisa los logs del servidor.', 'danger')
        return redirect(url_for('login'))


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
    categoria = request.form.get('categoria')
    precio = request.form.get('precio')
    descripcion = request.form.get('descripcion')
    fecha = (request.form.get('fecha') or '').strip()
    if not fecha:
        fecha = date.today().isoformat()  # yyyy-mm-dd

    usuario_id = session.get('id')  # quién lo agregó

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO productos (nombre, categoria, descripcion, precio, fecha, usuario_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (nombre, categoria, descripcion, precio, fecha, usuario_id))
        mysql.connection.commit()
        flash('Producto agregado correctamente.','success')
    finally:
        cursor.close()
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

# Edición/gestión con filtros y paginación
@app.route('/editarproductos')
def editarproductos():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    sort = request.args.get('sort', 'id_asc')
    search = request.args.get('search', '').strip()

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

    cursor = mysql.connection.cursor()
    try:
        count_sql = f"SELECT COUNT(*) as total FROM productos {where}"
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone().get('total') or 0

        total_pages = max(1, math.ceil(total_count / per_page))
        page = max(1, min(page, total_pages))
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

# ------------------- USUARIOS (admin) -------------------
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

    hashed = bcrypt.generate_password_hash(password).decode('utf-8')
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO usuario (nombre,email,password,id_rol,created_at,login_count,last_login)
            VALUES (%s,%s,%s,%s,NOW(),0,NULL)
        """, (nombre,email,hashed,2))
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
    password = (request.form.get('password') or '').strip()

    cursor = mysql.connection.cursor()
    try:
        if password:
            hashed = bcrypt.generate_password_hash(password).decode('utf-8')
            cursor.execute("UPDATE usuario SET nombre=%s,email=%s,password=%s WHERE id=%s",
                           (nombre,email,hashed,id))
        else:
            cursor.execute("UPDATE usuario SET nombre=%s,email=%s WHERE id=%s",
                           (nombre,email,id))
        mysql.connection.commit()
        flash('Usuario editado correctamente.','success')
    finally:
        cursor.close()
    return redirect(url_for('listausuarios'))

# ------------------- PERFIL ADMIN -------------------
@app.route('/perfil_admin')
def perfil_admin():
    if session.get('id_rol') != 1:
        flash('Acceso restringido solo para administradores.','danger')
        return redirect(url_for('login'))

    admin = None
    user_id = session.get('id')
    if user_id:
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("SELECT * FROM usuario WHERE id=%s", (user_id,))
            admin = cursor.fetchone()
        finally:
            cursor.close()
    return render_template('perfiladmin.html', admin=admin)

@app.route('/perfil_admin/editar', methods=['POST'], endpoint='editar_perfil_admin')
def editar_perfil_admin():
    if session.get('id_rol') != 1:
        flash('No autorizado.','danger')
        return redirect(url_for('login'))

    user_id = session.get('id')
    if not user_id:
        flash('No hay sesión activa.','danger')
        return redirect(url_for('login'))

    nombre = (request.form.get('nombre') or '').strip()
    email  = (request.form.get('email') or '').strip()
    password = (request.form.get('password') or '').strip()

    if not nombre or not email:
        flash('Nombre y correo son obligatorios.','warning')
        return redirect(url_for('perfil_admin'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT id FROM usuario WHERE email=%s AND id<>%s", (email, user_id))
        existe = cursor.fetchone()
        if existe:
            flash('El correo ya está en uso.','warning')
            return redirect(url_for('perfil_admin'))

        if password:
            hashed = bcrypt.generate_password_hash(password).decode('utf-8')
            cursor.execute("UPDATE usuario SET nombre=%s, email=%s, password=%s WHERE id=%s",
                           (nombre, email, hashed, user_id))
        else:
            cursor.execute("UPDATE usuario SET nombre=%s, email=%s WHERE id=%s",
                           (nombre, email, user_id))
        mysql.connection.commit()
        session['nombre'] = nombre
        flash('Perfil actualizado.','success')
    finally:
        cursor.close()

    return redirect(url_for('perfil_admin'))



if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG') == '1')
