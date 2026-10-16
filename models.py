from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

class Election(db.Model):
    __tablename__ = 'election'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False)
    conductor = db.Column(db.String(100), nullable=False)
    hours = db.Column(db.Float, nullable=False)
    rate_per_hour = db.Column(db.Float, default=499.0)
    total_cost = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    voters = db.relationship('Voter', backref='election', cascade='all, delete-orphan', lazy=True)
    candidates = db.relationship('Candidate', backref='election', cascade='all, delete-orphan', lazy=True)
    votes = db.relationship('Vote', backref='election', cascade='all, delete-orphan', lazy=True)

class Voter(db.Model):
    __tablename__ = 'voter'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    election_id = db.Column(db.Integer, db.ForeignKey('election.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    face_encoding = db.Column(db.PickleType, nullable=True)
    has_voted = db.Column(db.Boolean, default=False)

class Candidate(db.Model):
    __tablename__ = 'candidate'
    candidate_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    election_id = db.Column(db.Integer, db.ForeignKey('election.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    party = db.Column(db.String(100), nullable=False)
    logo_filename = db.Column(db.String(255), nullable=True)

class Vote(db.Model):
    __tablename__ = 'vote'
    vote_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    election_id = db.Column(db.Integer, db.ForeignKey('election.id'), nullable=False)
    voter_id = db.Column(db.Integer, db.ForeignKey('voter.id'), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.candidate_id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
