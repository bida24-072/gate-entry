@router.get("/students/{student_no}")
def get_student(student_no: str, db: Session = Depends(get_db), user: User = Depends(registrar)):
    s = _student(db, student_no)
    creds = db.scalars(select(Credential).where(Credential.student_id == s.id).order_by(Credential.id)).all()
    vehicles = db.scalars(select(Vehicle).where(Vehicle.student_id == s.id).order_by(Vehicle.id)).all()
    return {
        "student_no": s.student_no,
        "full_name": s.full_name,
        "status": s.status,
        "inside": s.inside,
        "credentials": [{"id": c.id, "type": c.type, "revoked": c.revoked_at is not None} for c in creds],
        "vehicles": [{"id": v.id, "plate": v.plate, "status": v.status} for v in vehicles],
    }
