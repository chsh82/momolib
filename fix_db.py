from app import create_app
from app.models import db

app = create_app()


def run(c, sql):
    try:
        c.execute(db.text(sql))
        print("OK:", sql[:50])
    except Exception as e:
        print("SKIP:", str(e)[:80])


with app.app_context():
    db.create_all()
    print("Tables created!")
    with db.engine.connect() as c:
        run(c,
            "ALTER TABLE student_profiles"
            " ADD COLUMN IF NOT EXISTS"
            " mileage INTEGER NOT NULL DEFAULT 0")
        run(c,
            "ALTER TABLE reading_mbti_questions"
            " ADD COLUMN IF NOT EXISTS options JSON")
        run(c,
            "ALTER TABLE reading_mbti_results"
            " ADD COLUMN IF NOT EXISTS scores JSON")
        run(c,
            "ALTER TABLE reading_mbti_types"
            " ADD COLUMN IF NOT EXISTS"
            " combo_description VARCHAR(200)")
        run(c,
            "ALTER TABLE reading_mbti_types"
            " ADD COLUMN IF NOT EXISTS"
            " full_description TEXT")
        run(c,
            "ALTER TABLE reading_mbti_types"
            " ADD COLUMN IF NOT EXISTS"
            " reading_style TEXT")
        run(c,
            "ALTER TABLE reading_mbti_types"
            " ADD COLUMN IF NOT EXISTS"
            " speaking_style TEXT")
        run(c,
            "ALTER TABLE reading_mbti_types"
            " ADD COLUMN IF NOT EXISTS"
            " writing_style TEXT")
        run(c,
            "ALTER TABLE reading_mbti_types"
            " ADD COLUMN IF NOT EXISTS tips JSON")
        run(c,
            "ALTER TABLE reading_mbti_types"
            " ALTER COLUMN strengths"
            " TYPE JSON USING strengths::json")
        run(c,
            "ALTER TABLE reading_mbti_types"
            " ALTER COLUMN weaknesses"
            " TYPE JSON USING weaknesses::json")
        run(c,
            "ALTER TABLE student_profiles"
            " ADD COLUMN IF NOT EXISTS"
            " streak_days INTEGER NOT NULL DEFAULT 0")
        run(c,
            "ALTER TABLE student_profiles"
            " ADD COLUMN IF NOT EXISTS"
            " last_active_date DATE")
        run(c, """
            CREATE TABLE IF NOT EXISTS book_mbti_results (
                result_id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                type_code VARCHAR(20) NOT NULL,
                scores JSON,
                taken_at TIMESTAMP DEFAULT NOW()
            )""")
        run(c, "CREATE INDEX IF NOT EXISTS ix_book_mbti_results_user_id ON book_mbti_results(user_id)")
        c.commit()
        print("완료!")
