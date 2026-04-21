from app.models.user import User, UserRole  # noqa: F401
from app.models.course import Course, CourseMaterial, Chunk, CourseStatus, MaterialType  # noqa: F401
from app.models.question import Question, QuestionType, QuestionDifficulty  # noqa: F401
from app.models.exam import Exam, ExamAttempt, ExamAnswer, ExamStatus  # noqa: F401
from app.models.record import LearningRecord, LearningAction  # noqa: F401
from app.models.feedback import AnswerFeedback, FeedbackRating  # noqa: F401
from app.models.knowledge import (  # noqa: F401
    KnowledgeSpace,
    KnowledgeSpaceStatus,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    KnowledgeRevision,
    KnowledgeRevisionStatus,
    KnowledgeSourceLink,
    KnowledgeConflict,
    KnowledgeConflictType,
    KnowledgeConflictStatus,
)
