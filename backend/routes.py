from . import app
import os
import json
from flask import jsonify, request
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from bson import json_util
import sys

# Load and setup MongoDB
SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
json_url = os.path.join(SITE_ROOT, "data", "songs.json")
songs_list = json.load(open(json_url))

mongodb_service = os.environ.get('MONGODB_SERVICE')
mongodb_username = os.environ.get('MONGODB_USERNAME')
mongodb_password = os.environ.get('MONGODB_PASSWORD')

print(f'The value of MONGODB_SERVICE is: {mongodb_service}')

if mongodb_service is None:
    app.logger.error('Missing MongoDB server in the MONGODB_SERVICE variable')
    sys.exit(1)

if mongodb_username and mongodb_password:
    url = f"mongodb://{mongodb_username}:{mongodb_password}@{mongodb_service}"
else:
    url = f"mongodb://{mongodb_service}"

print(f"Connecting to url: {url}")

try:
    client = MongoClient(url)
    print("MongoDB connection successful")
except OperationFailure as e:
    app.logger.error(f"Authentication error: {str(e)}")
    sys.exit(1)

db = client.songs
db.songs.drop()
db.songs.insert_many(songs_list)

def parse_json(data):
    return json.loads(json_util.dumps(data))

@app.route("/health")
def healthz():
    return jsonify({"status": "OK"}), 200

@app.route("/count")
def count():
    """Return length of data"""
    count = db.songs.count_documents({})
    return jsonify({"count": count}), 200

@app.route("/song", methods=["GET"])
def songs():
    results = list(db.songs.find({}))
    return jsonify({"songs": parse_json(results)}), 200

@app.route("/song/<int:id>", methods=["GET"])
def get_song_by_id(id):
    song = db.songs.find_one({"id": id})
    if not song:
        return jsonify({"message": f"Song with id {id} not found"}), 404
    return jsonify(parse_json(song)), 200

@app.route("/song", methods=["POST"])
def create_song():
    try:
        song_in = request.json

        if 'id' not in song_in or 'lyrics' not in song_in or 'title' not in song_in:
            return jsonify({"error": "Missing required fields"}), 400

        # Check if song with the same id already exists
        existing_song = db.songs.find_one({"id": song_in["id"]})
        if existing_song:
            return jsonify({"message": f"Song with id {song_in['id']} already present"}), 302

        # Insert the new song
        insert_id = db.songs.insert_one(song_in)
        return jsonify({"inserted_id": str(insert_id.inserted_id)}), 201
    
    except Exception as e:
        app.logger.error(f"Error creating song: {str(e)}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route("/song/<int:id>", methods=["PUT"])
def update_song(id):
    """Update an existing song by ID."""
    try:
        song_in = request.json

        # Ensure that the required fields are present
        if 'lyrics' not in song_in or 'title' not in song_in:
            return jsonify({"error": "Missing required fields"}), 400

        # Check if the song exists
        song = db.songs.find_one({"id": id})
        if not song:
            return jsonify({"message": "Song not found"}), 404

        # Update the song
        updated_data = {"$set": song_in}
        result = db.songs.update_one({"id": id}, updated_data)

        if result.matched_count == 0:
            return jsonify({"message": "Song found, but nothing updated"}), 200
        
        updated_song = db.songs.find_one({"id": id})
        return jsonify(parse_json(updated_song)), 200

    except Exception as e:
        app.logger.error(f"Error updating song: {str(e)}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route("/song/<int:id>", methods=["DELETE"])
def delete_song(id):

    result = db.songs.delete_one({"id": id})
    if result.deleted_count == 0:
        return {"message": "song not found"}, 404
    else:
        return "", 204