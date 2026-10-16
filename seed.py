from app import app
from models import db, Election, Voter, Candidate

def seed_data():
    with app.app_context():
        print("Dropping existing tables and recreating database schema...")
        db.drop_all()
        db.create_all()

        # 1. Create Elections
        election1 = Election(
            name="College Student Election 2026",
            conductor="Principal Sharma",
            hours=3.0,
            rate_per_hour=499.0,
            total_cost=1497.0,
            is_active=True
        )

        election2 = Election(
            name="Department Head Vote",
            conductor="HR Admin",
            hours=1.0,
            rate_per_hour=499.0,
            total_cost=499.0,
            is_active=True
        )

        db.session.add_all([election1, election2])
        db.session.commit()

        # 2. Add Candidates
        candidates = [
            # Election 1 Candidates (College Student Election)
            Candidate(election_id=election1.id, name="Aarav Mehta", party="Student Unity Front", logo_filename="pa_logo.svg"),
            Candidate(election_id=election1.id, name="Priya Sen", party="Youth Progress Alliance", logo_filename="nyf_logo.svg"),
            Candidate(election_id=election1.id, name="Rohan Das", party="Campus Innovators", logo_filename="dp_logo.svg"),
            
            # Election 2 Candidates (Department Head Vote)
            Candidate(election_id=election2.id, name="Dr. Anita Roy", party="Research & Academic Excellence", logo_filename="gfp_logo.svg"),
            Candidate(election_id=election2.id, name="Prof. Vikram Seth", party="Applied Engineering Guild", logo_filename="pv_logo.svg"),
        ]

        # 3. Add Voters without face encodings (conductor registers faces via /setup)
        voters = [
            # Election 1 Voters
            Voter(election_id=election1.id, name="Manikanta", age=19, face_encoding=None),
            Voter(election_id=election1.id, name="Ansh Patel", age=20, face_encoding=None),
            Voter(election_id=election1.id, name="P. Kavya", age=19, face_encoding=None),
            Voter(election_id=election1.id, name="K. Govardhan", age=21, face_encoding=None),
            Voter(election_id=election1.id, name="L. Nagalaxshmi", age=20, face_encoding=None),

            # Election 2 Voters
            Voter(election_id=election2.id, name="Dr. Balakrishna", age=45, face_encoding=None),
            Voter(election_id=election2.id, name="D. Pradeep", age=38, face_encoding=None),
            Voter(election_id=election2.id, name="Akhil Kumar", age=42, face_encoding=None),
        ]

        db.session.add_all(candidates)
        db.session.add_all(voters)
        db.session.commit()

        print("\n" + "=" * 60)
        print("DATABASE SEEDING SUCCESSFUL!")
        print("=" * 60)
        print(f"\n[ELECTION 1] - ID: {election1.id}")
        print(f"Title:        {election1.name}")
        print(f"Conductor:    {election1.conductor}")
        print(f"Duration:     {election1.hours} hours (INR {election1.total_cost:.2f})")
        print(f"Candidates:   3 added")
        print(f"Voters:       5 added (Awaiting Face Registration)")
        print(f"Setup URL:    http://127.0.0.1:5001/setup/{election1.id}")
        print(f"Vote Portal:  http://127.0.0.1:5001/vote/{election1.id}")
        print(f"Results URL:  http://127.0.0.1:5001/admin/results/{election1.id}")

        print(f"\n[ELECTION 2] - ID: {election2.id}")
        print(f"Title:        {election2.name}")
        print(f"Conductor:    {election2.conductor}")
        print(f"Duration:     {election2.hours} hour (INR {election2.total_cost:.2f})")
        print(f"Candidates:   2 added")
        print(f"Voters:       3 added (Awaiting Face Registration)")
        print(f"Setup URL:    http://127.0.0.1:5001/setup/{election2.id}")
        print(f"Vote Portal:  http://127.0.0.1:5001/vote/{election2.id}")
        print(f"Results URL:  http://127.0.0.1:5001/admin/results/{election2.id}")

        print("\n" + "=" * 60)
        print("Admin Portal URL: http://127.0.0.1:5001/admin (PIN: 12345)")
        print("All Elections:    http://127.0.0.1:5001/admin/results")
        print("=" * 60 + "\n")

if __name__ == '__main__':
    seed_data()
