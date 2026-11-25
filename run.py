"""Start SkySentry:  python run.py   ->  http://localhost:5000"""
from skysentry import create_app
from skysentry.config import Config

app = create_app()

if __name__ == "__main__":
    print("🛰️  SkySentry is running  ->  http://localhost:%d" % Config.PORT)
    print("    No API keys needed: data comes from the free Open-Meteo APIs.")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
