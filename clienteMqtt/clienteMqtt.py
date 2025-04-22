import asyncio, ssl, certifi, logging, os, sys
import aiomqtt

logging.basicConfig(format='%(asctime)s - cliente mqtt - %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%d/%m/%Y %H:%M:%S')

async def topico_uno(topico1):
    while True:
        message = await topico1.get()
        logging.info(f"{message.topic}: {message.payload.decode('utf-8')}")

async def topico_dos(topico2):
    while True:
        message = await topico2.get()
        logging.info(f"{message.topic}: {message.payload.decode('utf-8')}")

async def admin(client, topico1, topico2):
    while True:
        async for message in client.messages:
            if message.topic.matches(os.environ['TOPICO1']):
                topico1.put_nowait(message)
            elif message.topic.matches(os.environ['TOPICO2']):
                topico2.put_nowait(message)

async def publicacion(client, contador):
    while True:
        valor = contador[0]
        await client.publish(os.environ['PUBLICAR'], str(valor))
        logging.info(f"{os.environ['PUBLICAR']}: {valor}")
        await asyncio.sleep(5)

async def tarea_contador(contador):
    while True:
        contador[0] += 1
        await asyncio.sleep(3)

async def run():
    tls_context = ssl.create_default_context(cafile=certifi.where())
    tls_context.check_hostname = True

    topico1 = asyncio.Queue()
    topico2 = asyncio.Queue()
    contador = [0]

    async with aiomqtt.Client(
        os.environ['SERVIDOR'],
        port=8883,
        tls_context=tls_context
    ) as client:
        await client.subscribe(os.environ['TOPICO1'])
        await client.subscribe(os.environ['TOPICO2'])

        await asyncio.gather(
            topico_uno(topico1),
            topico_dos(topico2),
            admin(client, topico1, topico2),
            publicacion(client, contador),
            tarea_contador(contador)
        )

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(0)
