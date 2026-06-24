from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = BASE_DIR / "users.json"
MIN_ENROLLMENT_SAMPLE_COUNT = 6
MIN_FIXED_TEXT_LENGTH = 10
MIN_VECTOR_STD_MS = 18.0
MIN_TOTAL_TIME_STD_MS = 45.0
DWELL_TIME_WEIGHT = 0.50
FLIGHT_TIME_WEIGHT = 0.30
TOTAL_TIME_WEIGHT = 0.20

@dataclass
class KeyInterval:
    press_time_ms: float
    release_time_ms: float

@dataclass
class KeystrokeSample:
    dwell_time_vector_ms: List[float]
    flight_time_vector_ms: List[float]
    total_typing_time_ms: float
    key_press_offsets_ms: List[float]

@dataclass
class UserKeystrokeProfile:
    fixed_text_length: int
    dwell_time_mean_vector_ms: List[float]
    dwell_time_std_vector_ms: List[float]
    flight_time_mean_vector_ms: List[float]
    flight_time_std_vector_ms: List[float]
    mean_total_typing_time_ms: float
    std_total_typing_time_ms: float
    mean_within_user_distance: float
    acceptance_threshold: float
    training_sample_count: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "UserKeystrokeProfile":
        return cls(
            fixed_text_length=int(data["fixed_text_length"]),
            dwell_time_mean_vector_ms=list(data["dwell_time_mean_vector_ms"]),
            dwell_time_std_vector_ms=list(data["dwell_time_std_vector_ms"]),
            flight_time_mean_vector_ms=list(data["flight_time_mean_vector_ms"]),
            flight_time_std_vector_ms=list(data["flight_time_std_vector_ms"]),
            mean_total_typing_time_ms=float(data["mean_total_typing_time_ms"]),
            std_total_typing_time_ms=float(data["std_total_typing_time_ms"]),
            mean_within_user_distance=float(data["mean_within_user_distance"]),
            acceptance_threshold=float(data["acceptance_threshold"]),
            training_sample_count=int(data["training_sample_count"]),
        )


@dataclass
class AuthenticationResult:
    is_authenticated: bool
    status_message: str
    hint_message: str
    details_message: str
    sample: Optional[KeystrokeSample] = None


UserRecord = Dict[str, object]

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def calculate_mean_value(values: List[float]) -> float:
    return mean(values) if values else 0.0


def calculate_standard_deviation(values: List[float], minimum_value: float) -> float:
    if len(values) < 2:
        return minimum_value
    return max(pstdev(values), minimum_value)

#TODO 1 - Имплементиране на изчисляването на основни времеви параметри
#Изчисляване на вектора от времена на задържане (dwell time).
def calculate_dwell_time_vector_ms(key_intervals: List[KeyInterval]) -> List[float]:
    return [round(interval.release_time_ms - interval.press_time_ms, 3) for interval in key_intervals]
#Изчисляване на вектора от времена между натисканията (flight time).
def calculate_flight_time_vector_ms(key_intervals: List[KeyInterval]) -> List[float]:
    return [
        round(key_intervals[index + 1].press_time_ms - key_intervals[index].release_time_ms, 3)
        for index in range(len(key_intervals) - 1)
    ]
#Изчисляване на общото време за въвеждане на фиксирания низ.
def calculate_total_typing_time_ms(key_intervals: List[KeyInterval]) -> float:
    return round(key_intervals[-1].release_time_ms - key_intervals[0].press_time_ms, 3)


def calculate_key_press_offsets_ms(key_intervals: List[KeyInterval]) -> List[float]:
    first_press_time_ms = key_intervals[0].press_time_ms
    return [round(interval.press_time_ms - first_press_time_ms, 3) for interval in key_intervals]

#TODO 2 - Имплементиране на изчисляването на статистически характеристики:
#Изчисляване на среден вектор за множество обучаващи проби.
def calculate_mean_vector(sample_vectors: List[List[float]]) -> List[float]:
    vector_length = len(sample_vectors[0])
    return [calculate_mean_value([vector[index] for vector in sample_vectors]) for index in range(vector_length)]
#Изчисляване на вектор от стандартни отклонения за профила.
def calculate_standard_deviation_vector(sample_vectors: List[List[float]], minimum_value: float) -> List[float]:
    vector_length = len(sample_vectors[0])
    return [
        calculate_standard_deviation([vector[index] for vector in sample_vectors], minimum_value)
        for index in range(vector_length)
    ]

# Изчисляване на нормализирана дистанция между проба и профил.
def calculate_average_normalized_distance(
    current_vector: List[float],
    mean_vector: List[float],
    std_vector: List[float],
    minimum_std_value: float,
) -> float:
    if not current_vector:
        return 0.0

    normalized_distances = [
        abs(current_value - mean_value) / max(std_value, minimum_std_value)
        for current_value, mean_value, std_value in zip(current_vector, mean_vector, std_vector)
    ]
    return calculate_mean_value(normalized_distances)

def calculate_weighted_authentication_score(
    keystroke_sample: KeystrokeSample,
    user_profile: UserKeystrokeProfile,
) -> Dict[str, float]:
    dwell_time_distance = calculate_average_normalized_distance(
        keystroke_sample.dwell_time_vector_ms,
        user_profile.dwell_time_mean_vector_ms,
        user_profile.dwell_time_std_vector_ms,
        MIN_VECTOR_STD_MS,
    )
    flight_time_distance = calculate_average_normalized_distance(
        keystroke_sample.flight_time_vector_ms,
        user_profile.flight_time_mean_vector_ms,
        user_profile.flight_time_std_vector_ms,
        MIN_VECTOR_STD_MS,
    )
    total_typing_time_distance = abs(
        keystroke_sample.total_typing_time_ms - user_profile.mean_total_typing_time_ms
    ) / max(user_profile.std_total_typing_time_ms, MIN_TOTAL_TIME_STD_MS)

    weighted_authentication_score = (
        dwell_time_distance * DWELL_TIME_WEIGHT
        + flight_time_distance * FLIGHT_TIME_WEIGHT
        + total_typing_time_distance * TOTAL_TIME_WEIGHT
    )

    return {
        "dwell_time_distance": round(dwell_time_distance, 3),
        "flight_time_distance": round(flight_time_distance, 3),
        "total_typing_time_distance": round(total_typing_time_distance, 3),
        "weighted_authentication_score": round(weighted_authentication_score, 3),
    }

# TODO 3 - Имплементиране на определянето на индивидуален праг за автентикация
# Определяне на индивидуален праг от вътрешната вариация на потребителя.
def calculate_individual_acceptance_threshold(within_user_scores: List[float]) -> float:
    mean_within_user_score = calculate_mean_value(within_user_scores)
    within_user_std = calculate_standard_deviation(within_user_scores, 0.15)
    return round(clamp(mean_within_user_score + 2 * within_user_std, 1.8, 4.0), 3)

def build_user_keystroke_profile(training_samples: List[KeystrokeSample]) -> UserKeystrokeProfile:
    if not training_samples:
        raise ValueError("At least one training sample is required.")

    fixed_text_length = len(training_samples[0].dwell_time_vector_ms)
    expected_flight_vector_length = len(training_samples[0].flight_time_vector_ms)

    for sample in training_samples:
        if len(sample.dwell_time_vector_ms) != fixed_text_length:
            raise ValueError("All dwell time vectors must have the same length.")
        if len(sample.flight_time_vector_ms) != expected_flight_vector_length:
            raise ValueError("All flight time vectors must have the same length.")

    dwell_time_vectors = [sample.dwell_time_vector_ms for sample in training_samples]
    flight_time_vectors = [sample.flight_time_vector_ms for sample in training_samples]
    total_typing_times = [sample.total_typing_time_ms for sample in training_samples]

    preliminary_profile = UserKeystrokeProfile(
        fixed_text_length=fixed_text_length,
        dwell_time_mean_vector_ms=calculate_mean_vector(dwell_time_vectors),
        dwell_time_std_vector_ms=calculate_standard_deviation_vector(dwell_time_vectors, MIN_VECTOR_STD_MS),
        flight_time_mean_vector_ms=calculate_mean_vector(flight_time_vectors),
        flight_time_std_vector_ms=calculate_standard_deviation_vector(flight_time_vectors, MIN_VECTOR_STD_MS),
        mean_total_typing_time_ms=calculate_mean_value(total_typing_times),
        std_total_typing_time_ms=calculate_standard_deviation(total_typing_times, MIN_TOTAL_TIME_STD_MS),
        mean_within_user_distance=0.0,
        acceptance_threshold=0.0,
        training_sample_count=len(training_samples),
    )

    within_user_scores = [
        calculate_weighted_authentication_score(sample, preliminary_profile)["weighted_authentication_score"]
        for sample in training_samples
    ]

    return UserKeystrokeProfile(
        fixed_text_length=fixed_text_length,
        dwell_time_mean_vector_ms=preliminary_profile.dwell_time_mean_vector_ms,
        dwell_time_std_vector_ms=preliminary_profile.dwell_time_std_vector_ms,
        flight_time_mean_vector_ms=preliminary_profile.flight_time_mean_vector_ms,
        flight_time_std_vector_ms=preliminary_profile.flight_time_std_vector_ms,
        mean_total_typing_time_ms=preliminary_profile.mean_total_typing_time_ms,
        std_total_typing_time_ms=preliminary_profile.std_total_typing_time_ms,
        mean_within_user_distance=round(calculate_mean_value(within_user_scores), 3),
        acceptance_threshold=calculate_individual_acceptance_threshold(within_user_scores),
        training_sample_count=len(training_samples),
    )


class UserRepository:
    def __init__(self, database_path: Path = DATABASE_FILE) -> None:
        self.database_path = database_path

    def load_users(self) -> Dict[str, UserRecord]:
        if not self.database_path.exists():
            return {}

        try:
            raw_data = json.loads(self.database_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

        if isinstance(raw_data, dict):
            return raw_data
        return {}

    def save_users(self, users: Dict[str, UserRecord]) -> None:
        self.database_path.write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")

    def list_usernames(self) -> List[str]:
        return sorted(self.load_users().keys())

    def get_user(self, username: str) -> Optional[UserRecord]:
        return self.load_users().get(username)

    def upsert_user(self, username: str, user_record: UserRecord) -> None:
        users = self.load_users()
        users[username] = user_record
        self.save_users(users)


class AuthService:
    def __init__(self, repository: Optional[UserRepository] = None) -> None:
        self.repository = repository or UserRepository()

    def list_usernames(self) -> List[str]:
        return self.repository.list_usernames()

    def user_exists(self, username: str) -> bool:
        return self.repository.get_user(username) is not None

    def validate_registration_inputs(self, username: str, fixed_text: str) -> Tuple[bool, str]:
        normalized_username = username.strip()

        if not normalized_username:
            return False, "Въведи username за новия потребител."
        if " " in normalized_username:
            return False, "Username не трябва да съдържа интервали."
        if len(fixed_text) < MIN_FIXED_TEXT_LENGTH:
            return False, f"Фиксираният низ трябва да е поне {MIN_FIXED_TEXT_LENGTH} символа."
        if any(character.isspace() for character in fixed_text):
            return False, "За по-стабилно демо използвай фиксиран низ без интервали."
        return True, ""

    def enroll_user(
        self,
        username: str,
        fixed_text: str,
        training_samples: List[KeystrokeSample],
    ) -> UserKeystrokeProfile:
        user_profile = build_user_keystroke_profile(training_samples)
        self.repository.upsert_user(
            username.strip(),
            {
                "secret_hash": hash_secret(fixed_text),
                "keystroke_profile": user_profile.to_dict(),
            },
        )
        return user_profile

    def summarize_sample(self, keystroke_sample: KeystrokeSample) -> str:
        return (
            f"dwell {calculate_mean_value(keystroke_sample.dwell_time_vector_ms):.0f} ms | "
            f"flight {calculate_mean_value(keystroke_sample.flight_time_vector_ms):.0f} ms | "
            f"общо {keystroke_sample.total_typing_time_ms:.0f} ms"
        )

    def validate_login_identity(self, username: str, fixed_text: str) -> Optional[AuthenticationResult]:
        normalized_username = username.strip()

        if not normalized_username:
            return AuthenticationResult(False, "Липсва username.", "Избери или въведи потребител.", "")

        user_record = self.repository.get_user(normalized_username)
        if user_record is None:
            return AuthenticationResult(False, "Няма такъв потребител.", "Създай профил в таба за регистрация.", "")

        if not fixed_text:
            return AuthenticationResult(False, "Липсва фиксиран низ.", "Въведи паролата и опитай отново.", "")

        if hash_secret(fixed_text) != user_record["secret_hash"]:
            return AuthenticationResult(
                False,
                "Невалидна парола.",
                "Текстовата автентикация не мина. Биометричната проверка не се изпълнява.",
                "",
            )

        return None

    def authenticate_login_attempt(
        self,
        username: str,
        fixed_text: str,
        keystroke_sample: KeystrokeSample,
    ) -> AuthenticationResult:
        precheck_result = self.validate_login_identity(username, fixed_text)
        if precheck_result is not None:
            return precheck_result

        user_record = self.repository.get_user(username.strip())
        user_profile = UserKeystrokeProfile.from_dict(user_record["keystroke_profile"])

        if len(keystroke_sample.dwell_time_vector_ms) != user_profile.fixed_text_length:
            return AuthenticationResult(
                False,
                "Невалидна дължина на пробата.",
                "Въведеният фиксиран низ не съвпада по дължина с профила.",
                "",
            )

        distance_scores = calculate_weighted_authentication_score(keystroke_sample, user_profile)
        weighted_authentication_score = distance_scores["weighted_authentication_score"]
        details_message = (
            f"Dwell distance: {distance_scores['dwell_time_distance']:.2f} | "
            f"Flight distance: {distance_scores['flight_time_distance']:.2f} | "
            f"Total time distance: {distance_scores['total_typing_time_distance']:.2f} | "
            f"Обща оценка: {weighted_authentication_score:.2f} | "
            f"Праг: {user_profile.acceptance_threshold:.2f}"
        )

        if weighted_authentication_score <= user_profile.acceptance_threshold:
            return AuthenticationResult(
                True,
                "Достъп разрешен: въведеният текст и поведенческият профил съвпадат.",
                "Автентикацията е приета по dwell time, flight time и общо време.",
                details_message,
                keystroke_sample,
            )

        return AuthenticationResult(
            False,
            "Достъп отказан: текстът е верен, но динамиката на писане не съвпада.",
            "Пробата е твърде далеч от референтния потребителски профил.",
            details_message,
            keystroke_sample,
        )
