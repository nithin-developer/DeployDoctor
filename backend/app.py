import os
import sys
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from config.database import init_app, db
from werkzeug.security import generate_password_hash
from datetime import datetime as dt
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp

# Models
from models.users import User

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-change')

# Allow multiple frontend origins (comma-separated) and common prod hosts
frontend_origins_env = os.getenv('FRONTEND_ORIGINS')
if frontend_origins_env:
    allowed_origins = [o.strip()
                       for o in frontend_origins_env.split(',') if o.strip()]
else:
    allowed_origins = [
        os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173'),
        'http://localhost:3000',
    ]

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": allowed_origins,
        }
    },
    supports_credentials=True,
    allow_headers=['Content-Type', 'Authorization'],
    expose_headers=['Content-Disposition'],
    methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
)
init_app(app)


def add_default_user():
    with app.app_context():
        email = "user@example.com"
        password = "password123"

        user = User.query.filter_by(email=email).first()
        if user:
            print(f"User with email {email} already exists.")
            return

        new_user = User(
            full_name="Default User",
            email=email,
            hashed_password=generate_password_hash(password),
        )
        db.session.add(new_user)
        db.session.commit()
        print(
            f"Default user created with email: {email} and password: {password}")


# Health check endpoint
@app.route('/api/health', methods=['GET'])
def get_health():
    return jsonify({"status": "healthy", "timestamp": dt.now()}), 200


# Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)


if __name__ == '__main__':
    if "--add-default-user" in sys.argv:
        add_default_user()
    else:
        app.run(debug=True, host='0.0.0.0', port=8000)
