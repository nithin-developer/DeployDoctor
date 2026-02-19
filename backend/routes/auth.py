import os
import datetime as dt
from functools import wraps
import uuid
import secrets
import jwt
import pyotp
from flask import Blueprint, request, jsonify, make_response
from werkzeug.security import check_password_hash, generate_password_hash
from models.users import User, RefreshToken
from config.database import db

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

JWT_SECRET = os.getenv('JWT_SECRET', 'dev-secret-change')
ACCESS_EXPIRES_MIN = int(os.getenv('ACCESS_EXPIRES_MIN', '15'))
REFRESH_EXPIRES_DAYS = int(os.getenv('REFRESH_EXPIRES_DAYS', '7'))


def create_tokens(user: User):
    now = dt.datetime.now(dt.timezone.utc)
    access_payload = {
        'sub': str(user.id),
        'email': user.email,
        'type': 'access',
        'iat': now,
        'exp': now + dt.timedelta(minutes=ACCESS_EXPIRES_MIN)
    }
    jti = secrets.token_hex(16)
    refresh_expires = now + dt.timedelta(days=REFRESH_EXPIRES_DAYS)
    refresh_payload = {
        'sub': str(user.id),
        'type': 'refresh',
        'jti': jti,
        'iat': now,
        'exp': refresh_expires
    }
    access_token = jwt.encode(access_payload, JWT_SECRET, algorithm='HS256')
    refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm='HS256')
    db.session.add(RefreshToken(user_id=user.id, token_id=jti, expires_at=refresh_expires))
    db.session.commit()
    return access_token, refresh_token, refresh_expires


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing token'}), 401
        token = auth_header.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            if payload.get('type') != 'access':
                return jsonify({'error': 'Invalid token type'}), 401
            user = User.query.get(uuid.UUID(payload['sub']))
            if not user or not user.is_active:
                return jsonify({'error': 'User not active'}), 401
            request.user = user
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except Exception:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return wrapper


def set_refresh_cookie(resp, refresh_token, exp_dt: dt.datetime):
    secure = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
    same_site = os.getenv('COOKIE_SAMESITE', 'Lax')
    resp.set_cookie('refresh_token', refresh_token, httponly=True,
                    secure=secure, samesite=same_site, expires=exp_dt, path='/api/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json(force=True)
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        if not email or not password:
            return jsonify({'error': 'email and password required'}), 400

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.hashed_password, password):
            return jsonify({'error': 'invalid_credentials'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'user_inactive'}), 401

        # 2FA check
        if user.is_2fa_enabled:
            now = dt.datetime.utcnow()
            twofa_payload = {
                'sub': str(user.id), 'type': '2fa', 'iat': now,
                'exp': now + dt.timedelta(minutes=5)
            }
            twofa_token = jwt.encode(twofa_payload, JWT_SECRET, algorithm='HS256')
            return jsonify({'twofa_required': True, 'twofa_token': twofa_token}), 200

        access, refresh, refresh_exp = create_tokens(user)
        resp = make_response(jsonify({
            'twofa_required': False,
            'access_token': access,
            'user': user.to_dict()
        }))
        set_refresh_cookie(resp, refresh, refresh_exp)
        return resp
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/verify-2fa', methods=['POST'])
def verify_2fa():
    data = request.get_json(force=True)
    token = data.get('twofa_token')
    code = (data.get('code') or '').strip()
    if not token or not code:
        return jsonify({'error': 'token and code required'}), 400
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        if payload.get('type') != '2fa':
            return jsonify({'error': 'invalid_twofa_token'}), 400
        user = User.query.get(uuid.UUID(payload['sub']))
        if not user or not user.is_2fa_enabled or not user.totp_secret:
            return jsonify({'error': '2fa_not_setup'}), 400
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(code, valid_window=1):
            return jsonify({'error': 'invalid_code'}), 401
        access, refresh, refresh_exp = create_tokens(user)
        resp = make_response(jsonify({'access_token': access, 'user': user.to_dict()}))
        set_refresh_cookie(resp, refresh, refresh_exp)
        return resp
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'twofa_token_expired'}), 401
    except Exception:
        return jsonify({'error': 'invalid_twofa_token'}), 400


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    refresh_token = request.cookies.get('refresh_token')
    if not refresh_token:
        return jsonify({'error': 'missing_refresh_cookie'}), 401
    try:
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=['HS256'])
        if payload.get('type') != 'refresh':
            return jsonify({'error': 'invalid_token_type'}), 401
        
        user = User.query.get(uuid.UUID(payload['sub']))
        if not user or not user.is_active:
            return jsonify({'error': 'user_inactive'}), 401
        
        rt = RefreshToken.query.filter_by(token_id=payload.get('jti'), user_id=user.id).first()
        if not rt or not rt.is_valid():
            return jsonify({'error': 'refresh_revoked'}), 401
        
        access, new_refresh, refresh_exp = create_tokens(user)
        rt.revoked = True
        db.session.commit()
        resp = make_response(jsonify({'access_token': access}))
        set_refresh_cookie(resp, new_refresh, refresh_exp)
        return resp
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'refresh_expired'}), 401
    except Exception:
        return jsonify({'error': 'invalid_refresh_token'}), 400


@auth_bp.route('/logout', methods=['POST'])
def logout():
    refresh_token = request.cookies.get('refresh_token')
    resp = make_response(jsonify({'success': True}))
    resp.set_cookie('refresh_token', '', expires=0, path='/api/auth')
    if refresh_token:
        try:
            payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=['HS256'])
            if payload.get('type') == 'refresh':
                rt = RefreshToken.query.filter_by(token_id=payload.get('jti')).first()
                if rt and not rt.revoked:
                    rt.revoked = True
                    db.session.commit()
        except Exception:
            pass
    return resp


@auth_bp.route('/me', methods=['GET'])
@token_required
def me():
    return jsonify({'user': request.user.to_dict()})


@auth_bp.route('/setup-2fa', methods=['POST'])
@token_required
def setup_2fa():
    """Generate TOTP secret and QR code for 2FA setup"""
    user = request.user
    try:
        secret = pyotp.random_base32()
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email,
            issuer_name="App"
        )
        user.totp_secret = secret
        db.session.commit()
        return jsonify({
            'secret': secret,
            'qr_code_uri': totp_uri
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to setup 2FA'}), 500


@auth_bp.route('/enable-2fa', methods=['POST'])
@token_required
def enable_2fa():
    """Enable 2FA after verifying TOTP token"""
    user = request.user
    try:
        data = request.get_json()
        token = data.get('token')
        if not token:
            return jsonify({'error': 'TOTP token is required'}), 400
        if not user.totp_secret:
            return jsonify({'error': '2FA setup not initiated. Please setup 2FA first.'}), 400
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(token, valid_window=1):
            return jsonify({'error': 'Invalid TOTP token'}), 400
        user.is_2fa_enabled = True
        db.session.commit()
        return jsonify({'message': '2FA has been successfully enabled'}), 200
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to enable 2FA'}), 500


@auth_bp.route('/disable-2fa', methods=['POST'])
@token_required
def disable_2fa():
    """Disable 2FA for the current user"""
    user = request.user
    try:
        user.is_2fa_enabled = False
        user.totp_secret = None
        db.session.commit()
        return jsonify({'message': '2FA has been disabled'}), 200
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to disable 2FA'}), 500


@auth_bp.route('/update-account', methods=['PUT'])
@token_required
def update_account():
    """Update account information (name, etc.)"""
    user = request.user
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        if 'full_name' in data:
            if not data['full_name'] or len(data['full_name'].strip()) < 2:
                return jsonify({'error': 'Full name must be at least 2 characters'}), 400
            if len(data['full_name'].strip()) > 100:
                return jsonify({'error': 'Full name must not exceed 100 characters'}), 400
            user.full_name = data['full_name'].strip()
        
        if 'email' in data and data['email'] != user.email:
            return jsonify({'error': 'Email changes are not allowed for security reasons'}), 400
        
        db.session.commit()
        return jsonify({
            'message': 'Account updated successfully',
            'user': user.to_dict()
        }), 200
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to update account'}), 500


@auth_bp.route('/change-password', methods=['POST'])
@token_required
def change_password():
    """Change user password"""
    user = request.user
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not current_password:
            return jsonify({'error': 'Current password is required'}), 400
        if not new_password:
            return jsonify({'error': 'New password is required'}), 400
        if not confirm_password:
            return jsonify({'error': 'Password confirmation is required'}), 400
        
        if len(new_password) < 6:
            return jsonify({'error': 'New password must be at least 6 characters'}), 400
        if new_password != confirm_password:
            return jsonify({'error': 'New password and confirmation do not match'}), 400
        
        if not check_password_hash(user.hashed_password, current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        user.hashed_password = generate_password_hash(new_password)
        db.session.commit()
        return jsonify({'message': 'Password changed successfully'}), 200
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to change password'}), 500
