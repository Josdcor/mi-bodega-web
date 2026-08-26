import customtkinter as ctk
import sqlite3
import pandas as pd
import requests
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MiBodegaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Control Pro - Mi Bodega V2")
        self.geometry("1250x850")
        
        self.tasa_bcv = 0.0
        self.rol_actual = "" 
        
        # Inicializamos la base de datos y obtenemos la tasa dólar
        self.inicializar_db()
        self.obtener_tasa_dolar() 
        
        self.withdraw() 
        self.ventana_login()

    def conectar_db(self):
        return sqlite3.connect("bodega.db")

    def inicializar_db(self):
        conn = self.conectar_db()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS productos 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         nombre TEXT, 
                         categoria TEXT DEFAULT 'General', 
                         precio REAL, 
                         stock_actual INTEGER, 
                         stock_minimo INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         producto_id INTEGER, 
                         tipo TEXT, 
                         cantidad INTEGER, 
                         fecha TEXT, 
                         responsable TEXT)''')
        conn.commit()
        conn.close()

    def obtener_tasa_dolar(self):
        try:
            response = requests.get("https://ve.dolarapi.com/v1/dolares/oficial")
            data = response.json()
            self.tasa_bcv = float(data['promedio'])
        except:
            self.tasa_bcv = 36.50 
            print("Usando tasa de respaldo.")

    def ventana_login(self):
        self.login = ctk.CTkToplevel()
        self.login.title("Acceso")
        self.login.geometry("400x550")
        self.login.attributes("-topmost", True)

        ctk.CTkLabel(self.login, text="👤", font=("Arial", 60)).pack(pady=(30, 10))
        ctk.CTkLabel(self.login, text="Control de Acceso", font=("Arial", 22, "bold")).pack(pady=10)

        self.user_entry = ctk.CTkEntry(self.login, placeholder_text="Usuario (Admin / Vendedor)", width=250, height=40)
        self.user_entry.pack(pady=10)
        self.pass_entry = ctk.CTkEntry(self.login, placeholder_text="Contraseña", show="*", width=250, height=40)
        self.pass_entry.pack(pady=10)

        def validar():
            u, c = self.user_entry.get(), self.pass_entry.get()
            if u == "Admin" and c == "1234":
                self.rol_actual = "Admin"
                iniciar()
            elif u == "Vendedor" and c == "0000":
                self.rol_actual = "Operador"
                iniciar()
            else:
                messagebox.showerror("Error", "Credenciales incorrectas")

        def iniciar():
            self.login.destroy()
            self.deiconify()
            self.configurar_interfaz_principal()
            self.mostrar_dashboard()

        ctk.CTkButton(self.login, text="Entrar", command=validar, width=250, height=45).pack(pady=20)

    def configurar_interfaz_principal(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar_frame = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar_frame, text="📦 MI BODEGA PRO", font=("Arial", 20, "bold")).pack(pady=30)
        
        self.btn_dash = ctk.CTkButton(self.sidebar_frame, text="Dashboard", command=self.mostrar_dashboard)
        self.btn_dash.pack(pady=10, padx=20, fill="x")

        self.btn_inv = ctk.CTkButton(self.sidebar_frame, text="Inventario", command=self.mostrar_inventario)
        self.btn_inv.pack(pady=10, padx=20, fill="x")

        if self.rol_actual == "Admin":
            self.btn_hist = ctk.CTkButton(self.sidebar_frame, text="Historial Admin", command=self.mostrar_historial)
            self.btn_hist.pack(pady=10, padx=20, fill="x")

        tasa_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="#2b2b2b", corner_radius=10)
        tasa_frame.pack(side="bottom", pady=20, padx=20, fill="x")
        ctk.CTkLabel(tasa_frame, text=f"Tasa BCV: {self.tasa_bcv:.2f} Bs.", font=("Arial", 14, "bold"), text_color="#f59e0b").pack(pady=10)

        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, padx=30, pady=30, sticky="nsew")

    def limpiar_pantalla(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()

    # --- DASHBOARD ---
    def mostrar_dashboard(self):
        self.limpiar_pantalla()
        total_p, valor_inv, stock_bajo = self.obtener_resumen_db()
        
        cards_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        cards_frame.pack(fill="x")
        cards_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.crear_tarjeta(cards_frame, 0, "Items", f"{total_p}", "#6366f1")
        valor_bs = valor_inv * self.tasa_bcv
        self.crear_tarjeta(cards_frame, 1, "Capital Total", f"${valor_inv:,.2f}\n{valor_bs:,.2f} Bs.", "#10b981")
        self.crear_tarjeta(cards_frame, 2, "Alertas", f"{stock_bajo}", "#ef4444")

        self.mostrar_grafica()

    def mostrar_grafica(self):
        try:
            conn = self.conectar_db()
            df = pd.read_sql_query("SELECT nombre, stock_actual FROM productos ORDER BY stock_actual DESC LIMIT 6", conn)
            conn.close()
            if not df.empty:
                fig, ax = plt.subplots(figsize=(6, 3), dpi=100)
                fig.patch.set_facecolor('#1a1a1a')
                ax.set_facecolor('#1a1a1a')
                barras = ax.bar(df['nombre'], df['stock_actual'], color='#818cf8')
                ax.bar_label(barras, padding=3, color='white', fontweight='bold')
                ax.tick_params(colors='white', labelsize=8)
                canvas = FigureCanvasTkAgg(fig, master=self.main_container)
                canvas.draw()
                canvas.get_tk_widget().pack(pady=20, fill="both", expand=True)
        except: pass

    def crear_tarjeta(self, master, col, titulo, valor, color):
        card = ctk.CTkFrame(master, corner_radius=15, border_width=2, border_color=color)
        card.grid(row=0, column=col, padx=10, sticky="nsew")
        ctk.CTkLabel(card, text=valor, font=("Arial", 22, "bold"), text_color=color).pack(pady=(15, 0))
        ctk.CTkLabel(card, text=titulo, font=("Arial", 12), text_color="gray").pack(pady=(0, 15))

    def obtener_resumen_db(self):
        conn = self.conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(precio * stock_actual) FROM productos")
        res = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM productos WHERE stock_actual <= stock_minimo")
        bajo = cursor.fetchone()[0] or 0
        conn.close()
        return res[0] or 0, res[1] or 0.0, bajo

    # --- INVENTARIO ---
    def mostrar_inventario(self):
        self.limpiar_pantalla()
        header = ctk.CTkFrame(self.main_container, fg_color="transparent")
        header.pack(fill="x", pady=10)
        
        self.entry_busqueda = ctk.CTkEntry(header, placeholder_text="Buscar producto...", width=250)
        self.entry_busqueda.pack(side="left")
        self.entry_busqueda.bind("<KeyRelease>", lambda e: self.cargar_datos_tabla(self.entry_busqueda.get()))

        if self.rol_actual == "Admin":
            ctk.CTkButton(header, text="📥 Descargar Excel", fg_color="#1d6f42", width=140, command=self.exportar_excel_descarga).pack(side="right", padx=5)
            ctk.CTkButton(header, text="+ Nuevo", fg_color="#10b981", width=80, command=self.ventana_agregar).pack(side="right", padx=5)
        
        ctk.CTkButton(header, text="⬇ Venta", fg_color="#f59e0b", width=80, command=self.registrar_salida).pack(side="right", padx=5)

        columnas = ("ID", "Nombre", "Precio $", "Precio Bs.", "Stock")
        self.tabla = ttk.Treeview(self.main_container, columns=columnas, show="headings")
        for col in columnas:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, anchor="center")
        self.tabla.pack(fill="both", expand=True)
        self.cargar_datos_tabla()

    def cargar_datos_tabla(self, filtro=""):
        for item in self.tabla.get_children():
            self.tabla.delete(item)
        conn = self.conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre, precio, stock_actual, stock_minimo FROM productos WHERE nombre LIKE ?", ('%' + filtro + '%',))
        for p in cursor.fetchall():
            precio_bs = p[2] * self.tasa_bcv
            self.tabla.insert("", "end", values=(p[0], p[1], f"${p[2]:.2f}", f"{precio_bs:,.2f} Bs.", p[3]))
        conn.close()

    def exportar_excel_descarga(self):
        try:
            conn = self.conectar_db()
            df = pd.read_sql_query("SELECT * FROM productos", conn)
            conn.close()
            
            df['Precio_Bs'] = df['precio'] * self.tasa_bcv
            
            archivo_ruta = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile=f"Reporte_Bodega_{datetime.now().strftime('%d_%m_%Y')}"
            )
            
            if archivo_ruta:
                df.to_excel(archivo_ruta, index=False)
                messagebox.showinfo("Éxito", "El reporte se ha descargado correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el archivo: {e}")

    def registrar_salida(self):
        sel = self.tabla.selection()
        if not sel: return
        v = self.tabla.item(sel)['values']
        if messagebox.askyesno("Venta", f"Vender 1 unidad de {v[1]}?"):
            conn = self.conectar_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE productos SET stock_actual = stock_actual - 1 WHERE id = ?", (v[0],))
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO movimientos (producto_id, tipo, cantidad, fecha, responsable) VALUES (?, 'Salida', 1, ?, ?)", (v[0], fecha, self.rol_actual))
            conn.commit()
            conn.close()
            self.cargar_datos_tabla()

    def ventana_agregar(self):
        vent = ctk.CTkToplevel(self)
        vent.title("Nuevo Producto")
        vent.geometry("350x450")
        vent.attributes("-topmost", True)
        ctk.CTkLabel(vent, text="Detalles del Producto", font=("Arial", 16, "bold")).pack(pady=10)
        
        e_nom = ctk.CTkEntry(vent, placeholder_text="Nombre")
        e_nom.pack(pady=5, padx=20, fill="x")
        e_pre = ctk.CTkEntry(vent, placeholder_text="Precio en $")
        e_pre.pack(pady=5, padx=20, fill="x")
        e_st = ctk.CTkEntry(vent, placeholder_text="Stock Inicial")
        e_st.pack(pady=5, padx=20, fill="x")
        e_mi = ctk.CTkEntry(vent, placeholder_text="Mínimo Alerta")
        e_mi.pack(pady=5, padx=20, fill="x")

        def guardar():
            try:
                conn = self.conectar_db()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO productos (nombre, categoria, precio, stock_actual, stock_minimo) VALUES (?, 'General', ?, ?, ?)",
                               (e_nom.get(), float(e_pre.get()), int(e_st.get()), int(e_mi.get())))
                conn.commit()
                conn.close()
                self.cargar_datos_tabla()
                vent.destroy()
                messagebox.showinfo("Éxito", "Producto registrado correctamente.")
            except Exception as e:
                messagebox.showerror("Error", f"Revisa los datos ingresados: {e}")

        ctk.CTkButton(vent, text="Guardar", command=guardar).pack(pady=20)

    def mostrar_historial(self):
        self.limpiar_pantalla()
        ctk.CTkLabel(self.main_container, text="Historial de Auditoría", font=("Arial", 28, "bold")).pack(anchor="w", pady=10)
        columnas = ("ID", "Producto", "Tipo", "Cant", "Fecha", "Usuario")
        tabla_hist = ttk.Treeview(self.main_container, columns=columnas, show="headings")
        for col in columnas:
            tabla_hist.heading(col, text=col)
            tabla_hist.column(col, anchor="center")
        tabla_hist.pack(fill="both", expand=True)
        conn = self.conectar_db()
        cursor = conn.cursor()
        cursor.execute('''SELECT m.id, p.nombre, m.tipo, m.cantidad, m.fecha, m.responsable 
                          FROM movimientos m JOIN productos p ON m.producto_id = p.id ORDER BY m.fecha DESC''')
        for fila in cursor.fetchall():
            tabla_hist.insert("", "end", values=fila)
        conn.close()

if __name__ == "__main__":
    app = MiBodegaApp()
    app.mainloop()