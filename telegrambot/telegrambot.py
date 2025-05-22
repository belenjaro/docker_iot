from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import logging, os, asyncio, aiomysql, traceback, locale, aiomqtt, ssl, certifi, json
import matplotlib.pyplot as plt
from io import BytesIO

# Token del bot desde variable de entorno
token = os.environ["TB_TOKEN"]

# Configurar logging
logging.basicConfig(format='%(asctime)s - TelegramBot - %(levelname)s - %(message)s', level=logging.INFO)

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("Se conectó: " + str(update.message.from_user.id))
    nombre = update.message.from_user.first_name or ""
    apellido = update.message.from_user.last_name or ""
    kb = [["Destello"], ["Modo"], ["Relé"]]
    await context.bot.send_message(
        update.message.chat.id,
        text="Bienvenido al Bot " + nombre + " " + apellido,
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

# Comando /about
async def acercade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(update.message.chat.id, text="Este bot fue creado para el curso de IoT FIO")

# Comando /kill
async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(context.args)
    if context.args and context.args[0] == '@e':
        await context.bot.send_animation(update.message.chat.id, "CgACAgEAAxkBAAOPZkuctzsWZVlDSNoP9PavSZmH5poAAmUCAALrx0lEVKaX7K-68Ns1BA")
        await asyncio.sleep(6)
        await context.bot.send_message(update.message.chat.id, text="¡¡¡Ahora están todos muertos!!!")
    else:
        await context.bot.send_message(update.message.chat.id, text="☠️ ¡¡¡Esto es muy peligroso!!! ☠️")

# Comando /setpoint
async def setpoint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(context.args)
    if not context.args:
        await context.bot.send_message(chat_id=update.message.chat.id, text="Por favor ingresa un valor numérico.")
        return
    try:
        setpoint_value = float(context.args[0])
        await context.bot.send_message(chat_id=update.message.chat.id, text=f"Cambiando el setpoint a: {setpoint_value}")
        payload = json.dumps({"setpoint": setpoint_value})
        await publicar(context, "setpoint", payload)
    except ValueError:
        await context.bot.send_message(chat_id=update.message.chat.id, text="El valor ingresado no es un número válido.")

# Comando /periodo
async def periodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(context.args)
    if not context.args:
        await context.bot.send_message(chat_id=update.message.chat.id, text="Por favor ingresa un valor numérico.")
        return
    try:
        periodo_value = float(context.args[0])
        await context.bot.send_message(chat_id=update.message.chat.id, text=f"Cambiando el periodo a: {periodo_value}")
        payload = json.dumps({"periodo": periodo_value})
        await publicar(context, "periodo", payload)
    except ValueError:
        await context.bot.send_message(chat_id=update.message.chat.id, text="El valor ingresado no es un número válido.")

# Publicación en MQTT
async def publicar(context: ContextTypes.DEFAULT_TYPE, topico: str, payload: str):
    client = context.application.bot_data.get("mqtt_client")
    if not client:
        logging.error("MQTT client no disponible en el contexto.")
        return
    try:
        await client.publish(topico, payload)
        logging.info(f"Publicado en MQTT: {topico} -> {payload}")
    except Exception as e:
        logging.error(f"Error al publicar en MQTT: {e}")
        traceback.print_exc()

# Manejo de botones simples
async def DMR(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    acciones = {
        "destello": "Encendiendo el LED",
        "modo": "Cambiando el modo",
        "relé": "Activando el relé"
    }
    await publicar(context, text, text)
    await context.bot.send_message(update.message.chat.id, text=acciones[text])

# Consulta de última medición
async def medicion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(update.message.text)
    sql = f"SELECT timestamp, {update.message.text} FROM mediciones ORDER BY timestamp DESC LIMIT 1"
    conn = await aiomysql.connect(
        host=os.environ["MARIADB_SERVER"],
        port=3306,
        user=os.environ["MARIADB_USER"],
        password=os.environ["MARIADB_USER_PASS"],
        db=os.environ["MARIADB_DB"]
    )
    async with conn.cursor() as cur:
        await cur.execute(sql)
        r = await cur.fetchone()
        unidad = 'ºC' if update.message.text == 'temperatura' else '%'
        await context.bot.send_message(
            update.message.chat.id,
            text=f"La última {update.message.text} es de {str(r[1]).replace('.', ',')} {unidad},\nregistrada a las {r[0]:%H:%M:%S %d/%m/%Y}"
        )
        logging.info(f"La última {update.message.text} es de {r[1]} {unidad}, medida a las {r[0]:%H:%M:%S %d/%m/%Y}")
    conn.close()

# Generación de gráfico
async def graficos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(update.message.text)
    sql = f"""
        SELECT timestamp, {update.message.text.split()[1]}
        FROM mediciones
        WHERE id MOD 2 = 0
        AND timestamp >= NOW() - INTERVAL 1 DAY
        AND sensor_id LIKE 'sensor_1'
        ORDER BY timestamp
    """
    conn = await aiomysql.connect(
        host=os.environ["MARIADB_SERVER"],
        port=3306,
        user=os.environ["MARIADB_USER"],
        password=os.environ["MARIADB_USER_PASS"],
        db=os.environ["MARIADB_DB"]
    )
    async with conn.cursor() as cur:
        await cur.execute(sql)
        filas = await cur.fetchall()
        fig, ax = plt.subplots(figsize=(7, 4))
        fecha, var = zip(*filas)
        ax.plot(fecha, var)
        ax.grid(True, which='both')
        ax.set_title(update.message.text, fontsize=14)
        ax.set_xlabel('Fecha')
        ax.set_ylabel('Unidad')
        buffer = BytesIO()
        fig.tight_layout()
        fig.savefig(buffer, format='png')
        plt.close()
        buffer.seek(0)
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=buffer)
        buffer.close()
    conn.close()

# Función principal
async def main():
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.check_hostname = True
    tls_context.load_default_certs()

    async with aiomqtt.Client(
        os.environ["DOMINIO"],
        username=os.environ["MQTT_USR"],
        password=os.environ["MQTT_PASS"],
        port=int(os.environ["PUERTO_MQTTS"]),
        tls_context=tls_context,
    ) as client:

        application = Application.builder().token(token).build()

        # Handlers de comandos y mensajes
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('about', acercade))
        application.add_handler(CommandHandler('setpoint', setpoint))
        application.add_handler(CommandHandler('periodo', periodo))
        application.add_handler(CommandHandler('kill', kill))
        application.add_handler(MessageHandler(filters.Regex("^(Destello|Modo|Relé)$"), DMR))
        application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(temperatura|humedad)$"), medicion))
        application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^grafico "), graficos))

        application.bot_data["mqtt_client"] = client

        async with application:
            await application.start()
            await application.updater.start_polling()
            try:
                while True:
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                logging.info("Cerrando aplicación...")
            finally:
                await application.updater.stop()
                await application.stop()

# Ejecutar
if __name__ == "__main__":
    asyncio.run(main())
