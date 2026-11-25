"""Start SkySentry:  python run.py   ->  http://localhost:5000"""
from skysentry import create_app
from skysentry.config import Config

app = create_app()

if __name__ == "__main__":
    print("🛰️  SkySentry is starting...")
    print(f"   🌫️  Air Quality  ->  http://localhost:{Config.PORT}/")
    print(f"   🌤️  Weather      ->  http://localhost:{Config.PORT}/weather")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
