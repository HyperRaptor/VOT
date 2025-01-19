import os
import logging
from flask import Flask, request, jsonify
from minio import Minio
from minio.error import S3Error
import requests
from functools import wraps

app = Flask(__name__)

MINIO_URL = os.getenv('MINIO_URL', 'minio:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
REALM_NAME = 'your-realm'
CLIENT_ID = 'your-client-id'
CLIENT_SECRET = 'your-client-secret'

minio_client = Minio(MINIO_URL,
                     access_key=MINIO_ACCESS_KEY,
                     secret_key=MINIO_SECRET_KEY,
                     secure=False)

logging.basicConfig(level=logging.DEBUG)

def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 403
        token = token.split(' ')[1]
        
        try:
            response = requests.post(
                f'{KEYCLOAK_URL}/realms/{REALM_NAME}/protocol/openid-connect/token/introspect',
                data={'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'token': token}
            )
            if response.status_code != 200 or not response.json().get('active'):
                return jsonify({'message': 'Invalid or expired token!'}), 401
        except Exception as e:
            logging.error(f"Error verifying token: {e}")
            return jsonify({'message': 'Failed to verify token!'}), 500

        return f(*args, **kwargs)

    return decorated_function

@app.route('/upload', methods=['POST'])
@jwt_required
def upload_file():
    file = request.files.get('file')
    if not file:
        return jsonify({'message': 'No file part'}), 400
    
    file_id = file.filename
    try:
        minio_client.put_object('my-bucket', file_id, file, len(file.read()))
        file.seek(0)
        logging.info(f"File uploaded: {file_id}")
        return jsonify({'message': 'File uploaded successfully!', 'file_id': file_id}), 200
    except S3Error as e:
        logging.error(f"MinIO upload error: {e}")
        return jsonify({'message': 'Failed to upload file'}), 500

@app.route('/download/<file_id>', methods=['GET'])
@jwt_required
def download_file(file_id):
    try:
        file = minio_client.get_object('my-bucket', file_id)
        return file, 200
    except S3Error as e:
        logging.error(f"MinIO download error: {e}")
        return jsonify({'message': 'File not found'}), 404

@app.route('/update/<file_id>', methods=['PUT'])
@jwt_required
def update_file(file_id):
    file = request.files.get('file')
    if not file:
        return jsonify({'message': 'No file part'}), 400
    
    try:
        minio_client.put_object('my-bucket', file_id, file, len(file.read()))
        file.seek(0)
        logging.info(f"File updated: {file_id}")
        return jsonify({'message': 'File updated successfully!'}), 200
    except S3Error as e:
        logging.error(f"MinIO update error: {e}")
        return jsonify({'message': 'Failed to update file'}), 500

@app.route('/delete/<file_id>', methods=['DELETE'])
@jwt_required
def delete_file(file_id):
    try:
        minio_client.remove_object('my-bucket', file_id)
        logging.info(f"File deleted: {file_id}")
        return jsonify({'message': 'File deleted successfully!'}), 200
    except S3Error as e:
        logging.error(f"MinIO delete error: {e}")
        return jsonify({'message': 'Failed to delete file'}), 500

if __name__ == '__main__':
    if not minio_client.bucket_exists('my-bucket'):
        minio_client.make_bucket('my-bucket')
    app.run(debug=True, host='0.0.0.0', port=5000)
