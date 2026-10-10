from sqlalchemy.orm import Session

from src.db.models.user import User, UserProfile


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: str) -> User | None:
        return self.db.query(User).filter(User.user_id == user_id).first()

    def get_by_phone(self, phone_number: str) -> User | None:
        return self.db.query(User).filter(User.phone_number == phone_number).first()

    def get_profile(self, user_id: str) -> UserProfile | None:
        return self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    def get_or_create_profile(self, user_id: str) -> UserProfile:
        profile = self.get_profile(user_id)
        if profile:
            return profile

        profile = UserProfile(user_id=user_id)
        self.db.add(profile)
        return profile

    def add_user(self, user: User) -> User:
        self.db.add(user)
        return user

    def add_profile(self, profile: UserProfile) -> UserProfile:
        self.db.add(profile)
        return profile

    def delete_user(self, user: User) -> None:
        self.db.delete(user)
