import os
import threading
from app import app
from update_prices import job as update_job
import schedule
import time

def run_price_updates():
    """Thread para atualização de preços"""
    while True:
        try:
            update_job()  # Executa imediatamente na primeira vez
            schedule.every(1).hour.do(update_job)
            
            while True:
                schedule.run_pending()
                time.sleep(60)  # Verifica a cada minuto
        except Exception as e:
            print(f"Erro no processo de atualização: {e}")
            time.sleep(300)  # Espera 5 minutos antes de tentar novamente

def run_flask():
    """Thread para o servidor Flask"""
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Inicia thread de atualização de preços
    update_thread = threading.Thread(target=run_price_updates)
    update_thread.daemon = True
    update_thread.start()
    
    # Inicia o servidor Flask com Gunicorn
    from gunicorn.app.base import BaseApplication

    class FlaskApplication(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                self.cfg.set(key, value)

        def load(self):
            return self.application

    options = {
        'bind': '0.0.0.0:' + str(os.environ.get("PORT", 5000)),
        'workers': 3,
        'timeout': 120,
        'worker_class': 'sync'
    }

    FlaskApplication(app, options).run() 