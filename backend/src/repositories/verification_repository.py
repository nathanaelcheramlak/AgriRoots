from datetime import datetime

from sqlalchemy.orm import Session

from src.db.models.user import OTPVerification, PasswordResetVerification, PhoneChangeVerification


class OTPVerificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def consume_active_for_phone(self, phone_number: str) -> None:
        self.db.query(OTPVerification).filter(
            OTPVerification.phone_number == phone_number,
            OTPVerification.consumed.is_(False),
        ).update({OTPVerification.consumed: True}, synchronize_session=False)

    def get_latest_active(self, phone_number: str) -> OTPVerification | None:
        return (
            self.db.query(OTPVerification)
            .filter(
                OTPVerification.phone_number == phone_number,
                OTPVerification.consumed.is_(False),
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )

    def get_latest_verified(self, phone_number: str) -> OTPVerification | None:
        return (
            self.db.query(OTPVerification)
            .filter(
                OTPVerification.phone_number == phone_number,
                OTPVerification.consumed.is_(False),
                OTPVerification.verified.is_(True),
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )

    def add(self, verification: OTPVerification) -> OTPVerification:
        self.db.add(verification)
        return verification

    def delete_by_phone(self, phone_number: str) -> None:
        self.db.query(OTPVerification).filter(
            OTPVerification.phone_number == phone_number,
        ).delete(synchronize_session=False)


class PhoneChangeVerificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def consume_active_for_user(self, user_id: str) -> None:
        self.db.query(PhoneChangeVerification).filter(
            PhoneChangeVerification.user_id == user_id,
            PhoneChangeVerification.consumed.is_(False),
        ).update({PhoneChangeVerification.consumed: True}, synchronize_session=False)

    def get_recent_active(self, user_id: str, created_after: datetime) -> PhoneChangeVerification | None:
        return (
            self.db.query(PhoneChangeVerification)
            .filter(
                PhoneChangeVerification.user_id == user_id,
                PhoneChangeVerification.consumed.is_(False),
                PhoneChangeVerification.created_at >= created_after,
            )
            .order_by(PhoneChangeVerification.created_at.desc())
            .first()
        )

    def get_latest_active(self, user_id: str, new_phone_number: str) -> PhoneChangeVerification | None:
        return (
            self.db.query(PhoneChangeVerification)
            .filter(
                PhoneChangeVerification.user_id == user_id,
                PhoneChangeVerification.new_phone_number == new_phone_number,
                PhoneChangeVerification.consumed.is_(False),
            )
            .order_by(PhoneChangeVerification.created_at.desc())
            .first()
        )

    def add(self, verification: PhoneChangeVerification) -> PhoneChangeVerification:
        self.db.add(verification)
        return verification

    def delete_by_user(self, user_id: str) -> None:
        self.db.query(PhoneChangeVerification).filter(
            PhoneChangeVerification.user_id == user_id,
        ).delete(synchronize_session=False)


class PasswordResetVerificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def consume_active_for_phone(self, phone_number: str) -> None:
        self.db.query(PasswordResetVerification).filter(
            PasswordResetVerification.phone_number == phone_number,
            PasswordResetVerification.consumed.is_(False),
        ).update({PasswordResetVerification.consumed: True}, synchronize_session=False)

    def get_latest_active(self, phone_number: str) -> PasswordResetVerification | None:
        return (
            self.db.query(PasswordResetVerification)
            .filter(
                PasswordResetVerification.phone_number == phone_number,
                PasswordResetVerification.consumed.is_(False),
            )
            .order_by(PasswordResetVerification.created_at.desc())
            .first()
        )

    def get_latest_verified(self, phone_number: str) -> PasswordResetVerification | None:
        return (
            self.db.query(PasswordResetVerification)
            .filter(
                PasswordResetVerification.phone_number == phone_number,
                PasswordResetVerification.consumed.is_(False),
                PasswordResetVerification.verified.is_(True),
            )
            .order_by(PasswordResetVerification.created_at.desc())
            .first()
        )

    def add(self, verification: PasswordResetVerification) -> PasswordResetVerification:
        self.db.add(verification)
        return verification

    def delete_by_phone(self, phone_number: str) -> None:
        self.db.query(PasswordResetVerification).filter(
            PasswordResetVerification.phone_number == phone_number,
        ).delete(synchronize_session=False)
