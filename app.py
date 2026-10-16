from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, Election, Voter, Candidate, Vote
from datetime import datetime
import os
import random
from functools import wraps
import requests
import threading
import json
import math
import base64
import numpy as np
import tempfile

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

basedir = os.path.abspath(os.path.dirname(__file__)) 
app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = 'super-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'voting.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

ADMIN_PIN = "12345"

# Verify DeepFace is importable at startup — crash early with clear message if not
try:
    from deepface import DeepFace
    print("✅ DeepFace imported successfully at startup.")
except ImportError as e:
    print(f"❌ CRITICAL: DeepFace not available — {e}")
    print("❌ Check requirements.txt includes: deepface==0.0.93 and tf-keras")

def warmup_deepface():
    """Pre-download and cache the Facenet model on startup so first voter scan is not slow."""
    try:
        from deepface import DeepFace
        import numpy as np
        import tempfile, cv2, os

        # Create a blank 160x160 dummy image and run a fake represent call
        # This forces DeepFace to download Facenet weights on startup
        dummy = np.zeros((160, 160, 3), dtype=np.uint8)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
            cv2.imwrite(tmp_path, dummy)
        try:
            DeepFace.represent(
                img_path=tmp_path,
                model_name='Facenet',
                enforce_detection=False
            )
        except Exception:
            pass
        finally:
            os.unlink(tmp_path)
        print("✅ DeepFace Facenet model loaded and cached successfully.")
    except Exception as e:
        print(f"⚠️ DeepFace warmup failed (non-critical): {e}")

db.init_app(app)

with app.app_context():
    db.create_all()

import threading
threading.Thread(target=warmup_deepface, daemon=True).start()

# --- GOOGLE SHEETS SETTINGS ---
APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbxk0WCaopqz-5hPHaqowoZ6qbW40OUsKtk9gTzgNimDtAT8QeuUDVz8gYNWJbQHgBRT/exec'

def send_to_google_sheets(voter_name, voter_id, candidate_name, party, timestamp):
    try:
        data = {
            "voter_name": voter_name,
            "voter_id": str(voter_id),
            "candidate_name": candidate_name,
            "party": party,
            "timestamp": timestamp
        }
        res = requests.post(APPS_SCRIPT_URL, json=data, timeout=5)
        print("Google Sheets Sync:", res.text)
    except Exception as e:
        print(f"Error sending to Google Sheets: {e}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'voter_id' not in session:
            flash("Please login first.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def check_eligibility(voter):
    if not isinstance(voter, Voter):
        voter = db.session.get(Voter, voter)
    if not voter:
        return {"redirect": url_for('login')}
    if voter.age < 18:
        return {"redirect": url_for('not_eligible')}
    if voter.has_voted:
        return {"redirect": url_for('already_voted')}
    return None

def calculate_euclidean_distance(enc1, enc2):
    if len(enc1) != len(enc2): return 999.9
    sum_sq = sum((a - b) ** 2 for a, b in zip(enc1, enc2))
    return math.sqrt(sum_sq)

def get_face_embedding(image_data):
    """Decode base64 image and return face embedding using DeepFace."""
    if ',' in image_data:
        base64_str = image_data.split(',', 1)[1]
    else:
        base64_str = image_data

    image_bytes = base64.b64decode(base64_str)

    if cv2 is None:
        return None, "cv2 not available."

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None, "Invalid image format."

    if not DEEPFACE_AVAILABLE:
        return None, "DeepFace not available."

    try:
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
            cv2.imwrite(tmp_path, img)

        result = DeepFace.represent(
            img_path=tmp_path,
            model_name='Facenet',
            enforce_detection=True
        )
        os.unlink(tmp_path)
        embedding = result[0]['embedding']  # 128-dim list
        return embedding, None
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return None, f"No face detected: {str(e)}"

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

@app.route('/', methods=['GET'])
def login():
    session.pop('voter_id', None)
    session.pop('face_verified', None)
    session.pop('name', None)
    return render_template('login.html')

@app.route('/vote/<int:election_id>', methods=['GET'])
def vote_election(election_id):
    election = db.session.get(Election, election_id)
    if not election:
        return redirect(url_for('login'))
    if not election.is_active:
        return render_template('election_inactive.html', election=election)
    session['election_id'] = election.id
    session.pop('voter_id', None)
    session.pop('face_verified', None)
    session.pop('name', None)
    return render_template('vote_landing.html', election=election)

@app.route('/api/create-election', methods=['POST'])
def api_create_election():
    data = request.get_json() or {}
    election_name = data.get('election_name')
    conductor = data.get('conductor')
    hours = data.get('hours')

    if not election_name or not conductor or hours is None:
        return jsonify({"success": False, "message": "election_name, conductor, and hours are required."}), 400

    try:
        hours_val = float(hours)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "hours must be a valid number."}), 400

    if hours_val <= 0:
        return jsonify({"success": False, "message": "hours must be greater than 0."}), 400

    total_cost = hours_val * 499.0

    try:
        election = Election(
            name=str(election_name).strip(),
            conductor=str(conductor).strip(),
            hours=hours_val,
            rate_per_hour=499.0,
            total_cost=total_cost,
            is_active=True
        )
        db.session.add(election)
        db.session.commit()

        session['election_id'] = election.id
        return jsonify({
            "success": True, 
            "election_id": election.id,
            "redirect": url_for('setup', election_id=election.id)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500

@app.route('/setup/<int:election_id>', methods=['GET'])
def setup(election_id):
    if session.get('election_id') != election_id:
        return redirect(url_for('login'))
    
    election = db.session.get(Election, election_id)
    if not election:
        return redirect(url_for('login'))
    candidates = Candidate.query.filter_by(election_id=election_id).all()
    voters = Voter.query.filter_by(election_id=election_id).all()
    return render_template('setup.html', election=election, candidates=candidates, voters=voters)

@app.route('/api/<int:election_id>/add-candidate', methods=['POST'])
def api_add_candidate(election_id):
    if session.get('election_id') != election_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    election = db.session.get(Election, election_id)
    if not election:
        return jsonify({"success": False, "message": "Election not found."}), 404
        
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    party = (data.get('party') or '').strip()
    
    if not name or not party:
        return jsonify({"success": False, "message": "Candidate name and party are required."}), 400
        
    try:
        candidate = Candidate(
            election_id=election_id,
            name=name,
            party=party
        )
        db.session.add(candidate)
        db.session.commit()
        return jsonify({
            "success": True,
            "candidate": {
                "id": candidate.candidate_id,
                "name": candidate.name,
                "party": candidate.party
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500

@app.route('/api/<int:election_id>/remove-candidate/<int:candidate_id>', methods=['POST', 'DELETE'])
def api_remove_candidate(election_id, candidate_id):
    candidate = Candidate.query.filter_by(election_id=election_id, candidate_id=candidate_id).first()
    if not candidate:
        return jsonify({"success": False, "message": "Candidate not found."}), 404
    try:
        db.session.delete(candidate)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500

@app.route('/api/<int:election_id>/register-face', methods=['POST'])
def api_election_register_face(election_id):
    election = db.session.get(Election, election_id)
    if not election:
        return jsonify({"success": False, "message": "Election not found."}), 404

    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    age = data.get('age')
    image_data = data.get('image')

    if not name or age is None or not image_data:
        return jsonify({"success": False, "message": "name, age, and image are required."}), 400

    try:
        age_val = int(age)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Age must be a valid number."}), 400

    # Decode base64 image
    try:
        if ',' in image_data:
            base64_str = image_data.split(',', 1)[1]
        else:
            base64_str = image_data
        image_bytes = base64.b64decode(base64_str)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"success": False, "message": "Invalid image format."}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Image decode error: {str(e)}"}), 400

    # Get face embedding using DeepFace
    try:
        from deepface import DeepFace
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
            cv2.imwrite(tmp_path, img)
        try:
            result = DeepFace.represent(
                img_path=tmp_path,
                model_name='Facenet',
                enforce_detection=True
            )
            embedding = result[0]['embedding']  # 128-dim list
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as e:
        return jsonify({"success": False, "message": f"No face detected. Please look directly at the camera. ({str(e)})"}), 400

    # Check for duplicate face in this election
    existing_voters = Voter.query.filter_by(election_id=election_id).all()
    for v in existing_voters:
        if v.face_encoding is not None:
            try:
                existing_enc = v.face_encoding if isinstance(v.face_encoding, list) else json.loads(v.face_encoding)
                a = np.array(embedding)
                b = np.array(existing_enc)
                similarity = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
                if similarity > 0.7:
                    return jsonify({"success": False, "message": f"This face is already registered as '{v.name}'."}), 400
            except Exception:
                continue

    # Save voter with embedding
    try:
        voter = Voter(
            election_id=election_id,
            name=name,
            age=age_val,
            face_encoding=embedding
        )
        db.session.add(voter)
        db.session.commit()
        return jsonify({
            "success": True,
            "voter": {
                "id": voter.id,
                "name": voter.name
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500

@app.route('/setup/<int:election_id>/launch', methods=['GET', 'POST'])
def setup_launch_election(election_id):
    election = db.session.get(Election, election_id)
    if not election:
        return jsonify({"success": False, "message": "Election not found."}), 404
    election.is_active = True
    db.session.commit()
    session['election_launched'] = True
    return jsonify({
        "success": True,
        "vote_url": f"/vote/{election_id}"
    })

@app.route('/api/<int:election_id>/face-login', methods=['POST'])
def api_election_face_login(election_id):
    election = db.session.get(Election, election_id)
    if not election:
        return jsonify({"success": False, "error": "Election not found."}), 404
    if not election.is_active:
        return jsonify({"success": False, "error": "Election is not currently active."}), 400

    data = request.get_json() or {}
    image_data = data.get('image')

    if not image_data:
        return jsonify({"success": False, "error": "No image provided."}), 400

    # Decode base64 image
    try:
        if ',' in image_data:
            base64_str = image_data.split(',', 1)[1]
        else:
            base64_str = image_data
        image_bytes = base64.b64decode(base64_str)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"success": False, "error": "Invalid image format."}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Image decode error: {str(e)}"}), 400

    # Get face embedding using DeepFace
    try:
        from deepface import DeepFace
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
            cv2.imwrite(tmp_path, img)
        try:
            result = DeepFace.represent(
                img_path=tmp_path,
                model_name='Facenet',
                enforce_detection=True
            )
            query_embedding = result[0]['embedding']
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as e:
        return jsonify({"success": False, "error": f"Face not detected. Please look at camera. ({str(e)})"}), 400

    # Match against this election's voters only
    voters = Voter.query.filter_by(election_id=election_id).all()
    best_match = None
    best_similarity = 0.7  # minimum threshold to count as a match

    for v in voters:
        if v.face_encoding is None:
            continue
        try:
            db_enc = v.face_encoding if isinstance(v.face_encoding, list) else json.loads(v.face_encoding)
            a = np.array(query_embedding)
            b = np.array(db_enc)
            similarity = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = v
        except Exception:
            continue

    if not best_match:
        return jsonify({"success": False, "error": "Face not recognised. Please contact your polling officer."}), 401

    # Eligibility checks
    if best_match.age < 18:
        return jsonify({
            "success": False,
            "error": "Voter is under 18 and not eligible.",
            "redirect": url_for('not_eligible')
        }), 400

    if best_match.has_voted:
        return jsonify({
            "success": False,
            "error": "You have already cast your vote.",
            "redirect": url_for('already_voted')
        }), 400

    session['voter_id'] = best_match.id
    session['election_id'] = election_id
    session['name'] = best_match.name
    session['face_verified'] = True

    return jsonify({
        "success": True,
        "name": best_match.name,
        "redirect": url_for('vote')
    })

@app.route('/api/face-login', methods=['POST'])
def api_face_login():
    data = request.get_json() or {}
    descriptor = data.get('face_encoding')
    
    if not descriptor or len(descriptor) != 128:
        return jsonify({"success": False, "error": "Invalid face encoding."}), 400
        
    active_elec_id = session.get('election_id')
    if active_elec_id:
        voters = Voter.query.filter_by(election_id=active_elec_id).all()
    else:
        voters = Voter.query.all()

    best_match = None
    min_distance = 0.50
    
    for v in voters:
        if v.face_encoding is not None:
            if isinstance(v.face_encoding, str):
                try:
                    db_enc = json.loads(v.face_encoding)
                except Exception:
                    continue
            else:
                db_enc = v.face_encoding
            dist = calculate_euclidean_distance(descriptor, db_enc)
            if dist < min_distance:
                min_distance = dist
                best_match = v
                
    if best_match:
        eligibility = check_eligibility(best_match)
        if eligibility:
            session['voter_id'] = best_match.id
            session['election_id'] = best_match.election_id
            session['name'] = best_match.name
            return jsonify({"success": True, "redirect": eligibility['redirect']})
            
        session['voter_id'] = best_match.id
        session['election_id'] = best_match.election_id
        session['name'] = best_match.name
        session['face_verified'] = True
        return jsonify({"success": True, "redirect": url_for('vote')})
        
    return jsonify({"success": False, "error": "Face not recognized. Please register with an admin."}), 401

@app.route('/vote', methods=['GET'])
@login_required
def vote():
    if not session.get('face_verified'):
        return redirect(url_for('login'))
        
    voter = db.session.get(Voter, session['voter_id'])
    if not voter:
        return redirect(url_for('login'))
        
    eligibility = check_eligibility(voter)
    if eligibility: return redirect(eligibility['redirect'])
    
    election_id = session.get('election_id') or voter.election_id
    election = db.session.get(Election, election_id) if election_id else None
    candidates = Candidate.query.filter_by(election_id=election_id).all() if election_id else Candidate.query.all()
    return render_template('vote.html', candidates=candidates, election=election)

@app.route('/submit-vote', methods=['POST'])
@login_required
def submit_vote():
    if not session.get('face_verified'):
        return redirect(url_for('login'))
        
    voter = db.session.get(Voter, session['voter_id'])
    if not voter:
        return redirect(url_for('login'))
        
    eligibility = check_eligibility(voter)
    if eligibility: return redirect(eligibility['redirect'])
        
    candidate_id = request.form.get('candidate_id')
    if not candidate_id:
        flash("Please select a candidate.", "danger")
        return redirect(url_for('vote'))
        
    election_id = session.get('election_id') or voter.election_id

    try:
        new_vote = Vote(
            election_id=election_id,
            voter_id=voter.id,
            candidate_id=candidate_id
        )
        voter.has_voted = True
        db.session.add(new_vote)
        db.session.commit()
        
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session['vote_timestamp'] = timestamp_str
        
        candidate = db.session.get(Candidate, candidate_id)
        if APPS_SCRIPT_URL != 'https://script.google.com/macros/s/AKfycbxk0WCaopqz-5hPHaqowoZ6qbW40OUsKtk9gTzgNimDtAT8QeuUDVz8gYNWJbQHgBRT/exec' and candidate:
            threading.Thread(
                target=send_to_google_sheets, 
                args=(voter.name, voter.id, candidate.name, candidate.party, timestamp_str)
            ).start()
            
        return redirect(url_for('confirmation'))
    except Exception as e:
        db.session.rollback()
        flash("An error occurred while casting vote. Please try again.", "danger")
        return redirect(url_for('vote'))

@app.route('/confirmation', methods=['GET'])
@login_required
def confirmation():
    voter = db.session.get(Voter, session['voter_id'])
    if not voter or not voter.has_voted:
        return redirect(url_for('vote'))
    
    election_id = session.get('election_id') or voter.election_id
    election = db.session.get(Election, election_id) if election_id else None
    election_name = election.name if election else None

    timestamp = session.get('vote_timestamp', 'Unknown time')
    name = session.get('name')
    session.clear() 
    return render_template('confirmation.html', name=name, timestamp=timestamp, election_name=election_name)

@app.route('/already-voted')
def already_voted():
    return render_template('already_voted.html')

@app.route('/not-eligible')
def not_eligible():
    return render_template('not_eligible.html')


# === ADMIN ROUTES ===

@app.route('/admin')
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_results'))
    return render_template('admin_login.html')

@app.route('/admin/login', methods=['POST'])
def do_admin_login():
    pin = request.form.get('pin')
    if pin == ADMIN_PIN:
        session['admin_logged_in'] = True
        return redirect(url_for('admin_results'))
    flash("Invalid Admin PIN.", "danger")
    return redirect(url_for('admin_login'))

@app.route('/admin/results', defaults={'election_id': None}, methods=['GET'])
@app.route('/admin/results/<int:election_id>', methods=['GET'])
def admin_results(election_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
        
    if election_id is None:
        elections = Election.query.order_by(Election.id.desc()).all()
        elections_data = []
        for e in elections:
            voter_count = Voter.query.filter_by(election_id=e.id).count()
            votes_count = Vote.query.filter_by(election_id=e.id).count()
            elections_data.append({
                'id': e.id,
                'name': e.name,
                'conductor': e.conductor,
                'hours': e.hours,
                'total_cost': e.total_cost,
                'created_at': e.created_at,
                'is_active': e.is_active,
                'voter_count': voter_count,
                'votes_count': votes_count
            })
        return render_template('admin_elections.html', elections=elections_data)

    election = db.session.get(Election, election_id)
    if not election:
        flash("Election not found.", "warning")
        return redirect(url_for('admin_results'))

    candidates_data = []
    candidates = Candidate.query.filter_by(election_id=election_id).all()
    for c in candidates:
        count = Vote.query.filter_by(election_id=election_id, candidate_id=c.candidate_id).count()
        candidates_data.append({
            'name': c.name,
            'party': c.party,
            'logo_filename': c.logo_filename,
            'votes': count
        })
    
    labels = [f"{c['name']} ({c['party']})" for c in candidates_data]
    data = [c['votes'] for c in candidates_data]
    total_votes = sum(data)
        
    return render_template(
        'results.html', 
        election=election,
        labels=labels, 
        data=data, 
        candidates_data=candidates_data, 
        total_votes=total_votes
    )

@app.route('/admin/register-voter', methods=['GET'])
def admin_register_voter():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    return render_template('register_voter.html')

@app.route('/api/lookup-voter', methods=['GET'])
def api_lookup_voter():
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
        
    voter_id = request.args.get('voter_id')
    voter = db.session.get(Voter, voter_id) if voter_id else None
    
    if voter:
        return jsonify({"success": True, "name": voter.name, "age": voter.age})
    return jsonify({"success": False, "error": "Voter not found in system."})

@app.route('/api/register-face', methods=['POST'])
def api_register_face():
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
        
    data = request.get_json() or {}
    voter_id = data.get('voter_id')
    descriptor = data.get('face_encoding')
    
    if not voter_id or not descriptor or len(descriptor) != 128:
        return jsonify({"success": False, "error": "Invalid request parameters."})
        
    voter = db.session.get(Voter, voter_id)
    if not voter:
        return jsonify({"success": False, "error": "Voter not found."})
        
    try:
        voter.face_encoding = descriptor
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": "Database error."})

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    warmup_deepface()
    app.run(host='127.0.0.1', port=5001, debug=False)