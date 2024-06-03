from sqlalchemy import Column, BigInteger, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from passlib.hash import sha256_crypt

Base = declarative_base()


class User(Base):
    """Модель пользователя"""

    __tablename__ = "user_User"

    id = Column(
        BigInteger,
        primary_key=True,
        index=True,
        autoincrement=True,
        comment="Идентификатор пользователя",
    )
    name = Column(String, doc="Имя")
    soName = Column(String, doc="Фамилия")
    email = Column(String, doc="Emai")
    password = Column(String, doc="Password")

    forms = relationship("Form", back_populates="user")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "soName": self.soName,
        }

    def to_string(self):
        return f"{self.name} {self.soName}"

    def to_select(self):
        return {"value": self.id, "label": f"{self.name} {self.soName}"}

    def set_password(self):
        self.password = sha256_crypt.using(rounds=1000).hash(self.password)

    def verify_password(self, password):
        return sha256_crypt.verify(password, self.password)

    def __str__(self) -> str:
        return f"{self.name} {self.soName}"


class Form(Base):
    __tablename__ = "forms_forms"
    id = Column(BigInteger, primary_key=True, index=True)
    user_id_creat = Column(BigInteger, ForeignKey("user_User.id"), nullable=False)
    url = Column(String, nullable=False)

    user = relationship("User", back_populates="forms")
