/**
 * Phase 16f — Curriculum + Question Bank + Templates API helpers.
 *
 * Thin typed wrappers around the gateway endpoints introduced in
 * Phase 16. Used by the teacher-web `/curriculum` and
 * `/question-bank` routes.
 */
import { api } from "./api";

// ─── Curriculum ────────────────────────────────────────────────

export interface SchoolSubject {
  id: string;
  school_id: string;
  name: string;
  code: string;
  is_active: boolean;
  grade_levels: string[];
  national_subject_id: string | null;
}

export interface SchoolUnit {
  id: string;
  school_id: string;
  subject_id: string;
  name: string;
  code: string;
  sequence_order: number;
  grade_level: string | null;
  national_unit_id: string | null;
  description: string | null;
  topics?: SchoolTopic[];
}

export interface SchoolTopic {
  id: string;
  school_id: string;
  subject_id: string;
  unit_id: string;
  parent_topic_id: string | null;
  name: string;
  code: string;
  sequence_order: number;
  learning_outcomes: string | null;
  national_topic_id: string | null;
  subtopics?: SchoolTopic[];
}

export interface CurriculumTree {
  subject: SchoolSubject;
  units: SchoolUnit[];
}

export interface TopicResources {
  topic: { id: string; name: string; code: string; subject_id: string; unit_id: string };
  lesson_plans: Array<{ id: string; title: string; class_id: string | null; scheduled_date: string | null }>;
  homeworks: Array<{ id: string; title: string; class_id: string | null; due_date: string | null }>;
  assessments: Array<{ id: string; name: string; assessment_type: string; class_id: string | null; date: string | null }>;
  formative_assessments: Array<{ id: string; title: string; formative_kind: string; class_id: string | null }>;
  counts: { lesson_plans: number; homeworks: number; assessments: number; formative_assessments: number };
}

export interface NationalSubjectRow {
  id: string;
  country: string;
  code: string;
  name: string;
  description: string | null;
  ministry_published_at: string | null;
}

export const curriculumApi = {
  listSubjects: () =>
    api.get<SchoolSubject[]>("/api/v1/curriculum/subjects"),
  tree: (subject_id: string) =>
    api.get<CurriculumTree>("/api/v1/curriculum/tree", { subject_id }),
  createSubject: (body: { name: string; code: string; grade_levels?: string[] }) =>
    api.post<SchoolSubject>("/api/v1/curriculum/subjects", body),
  createUnit: (body: {
    subject_id: string;
    name: string;
    code: string;
    sequence_order?: number;
    grade_level?: string;
    description?: string;
  }) => api.post<SchoolUnit>("/api/v1/curriculum/units", body),
  createTopic: (body: {
    unit_id: string;
    name: string;
    code: string;
    sequence_order?: number;
    parent_topic_id?: string;
    learning_outcomes?: string;
  }) => api.post<SchoolTopic>("/api/v1/curriculum/topics", body),
  topicResources: (topic_id: string) =>
    api.get<TopicResources>(`/api/v1/curriculum/topics/${topic_id}/resources`),
  coverage: (subject_id: string) =>
    api.get<{
      subject_id: string;
      topics: Array<{
        topic_id: string;
        topic_name: string;
        topic_code: string;
        unit_id: string;
        lesson_plans: number;
        homeworks: number;
        assessments: number;
        formative_assessments: number;
        total: number;
      }>;
      uncovered_count: number;
    }>("/api/v1/curriculum/coverage", { subject_id }),
  adoptSubject: (body: {
    national_subject_id: string;
    grade_levels?: string[];
    code?: string;
    name?: string;
  }) =>
    api.post<{
      subject: SchoolSubject;
      units_cloned: number;
      topics_cloned: number;
      idempotent: boolean;
    }>("/api/v1/curriculum/adopt-subject", body),
  tagResource: (body: {
    resource_type: "lesson_plan" | "homework" | "assessment" | "formative_assessment";
    resource_id: string;
    topic_ids: string[];
  }) =>
    api.post<{
      resource_type: string;
      resource_id: string;
      topic_ids: string[];
    }>("/api/v1/curriculum/tag", body),

  // Ministry-side reference (read-only for school users).
  listNationalSubjects: (params?: { published_only?: boolean; country?: string }) =>
    api.get<NationalSubjectRow[]>(
      "/api/v1/ministry/national-curriculum/subjects",
      params as Record<string, string> | undefined,
    ),
  nationalSubjectTree: (subject_id: string) =>
    api.get<{
      subject: NationalSubjectRow;
      units: Array<SchoolUnit & { topics: SchoolTopic[] }>;
    }>(`/api/v1/ministry/national-curriculum/subjects/${subject_id}/tree`),
};

// ─── Question Bank ─────────────────────────────────────────────

export type QuestionType = "MCQ" | "TRUE_FALSE" | "SHORT_ANSWER";

export interface QuestionOption {
  id: string;
  label: string;
  text: string;
  is_correct: boolean;
  sequence_order: number;
}

export interface QuestionRow {
  id: string;
  school_id: string;
  subject_id: string;
  topic_ids: string[];
  question_type: QuestionType;
  text: string;
  correct_answer_text: string | null;
  difficulty: number;
  status: "draft" | "published" | "archived";
  owner_user_id: string;
  approved_by_hod_id: string | null;
  approved_at: string | null;
  attempts_count: number;
  correct_count: number;
  options: QuestionOption[];
}

export interface QuestionDraftRow {
  id: string;
  school_id: string;
  subject_id: string;
  topic_ids: string[];
  question_type: QuestionType;
  text: string;
  correct_answer_text: string | null;
  difficulty: number;
  options_json: Array<{ label: string; text: string; is_correct: boolean }>;
  submitted_by_user_id: string;
  submitted_at: string | null;
  review_status: "pending" | "approved" | "rejected";
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
  approved_question_id: string | null;
}

export const questionBankApi = {
  list: (params?: { subject_id?: string; topic_id?: string; question_type?: QuestionType; difficulty?: number }) =>
    api.get<QuestionRow[]>("/api/v1/questions", params as Record<string, string> | undefined),
  get: (id: string) =>
    api.get<QuestionRow>(`/api/v1/questions/${id}`),
  create: (body: {
    subject_id: string;
    topic_ids?: string[];
    question_type: QuestionType;
    text: string;
    correct_answer_text?: string;
    difficulty?: number;
    options?: Array<{ label: string; text: string; is_correct?: boolean }>;
  }) => api.post<QuestionRow>("/api/v1/questions", body),
  submitDraft: (body: {
    subject_id: string;
    topic_ids?: string[];
    question_type: QuestionType;
    text: string;
    correct_answer_text?: string;
    difficulty?: number;
    options?: Array<{ label: string; text: string; is_correct?: boolean }>;
  }) => api.post<QuestionDraftRow>("/api/v1/question-drafts", body),
  listDrafts: (status: "pending" | "approved" | "rejected" = "pending") =>
    api.get<QuestionDraftRow[]>("/api/v1/question-drafts", { status }),
  approveDraft: (id: string) =>
    api.post<{ draft: QuestionDraftRow; question_id: string }>(
      `/api/v1/question-drafts/${id}/approve`,
    ),
  rejectDraft: (id: string, reason: string) =>
    api.post<QuestionDraftRow>(`/api/v1/question-drafts/${id}/reject`, { reason }),

  composeAssessment: (assessment_id: string, body: {
    question_ids: string[];
    instructions?: string;
    exam_paper_attachment_id?: string;
  }) => api.post<{
    assessment_id: string;
    question_ids: string[];
    instructions: string | null;
    exam_paper_attachment_id: string | null;
  }>(`/api/v1/assessments/${assessment_id}/compose`, body),
};

// ─── Templates ─────────────────────────────────────────────────

export interface HomeworkTemplateRow {
  id: string;
  school_id: string;
  subject_id: string | null;
  title: string;
  description: string;
  default_due_days: number | null;
  topic_ids: string[];
  grade_levels: string[];
  is_published_school_wide: boolean;
  source_template_id: string | null;
  maintained_by_user_id: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface LessonPlanTemplateRow {
  id: string;
  school_id: string;
  subject_id: string | null;
  title: string;
  objectives: string | null;
  activities: string | null;
  resources: string | null;
  suggested_period_number: number | null;
  topic_ids: string[];
  grade_levels: string[];
  is_published_school_wide: boolean;
  source_template_id: string | null;
  maintained_by_user_id: string;
}

export const templatesApi = {
  listHomework: (params?: { subject_id?: string; published_only?: boolean; mine_only?: boolean }) =>
    api.get<HomeworkTemplateRow[]>(
      "/api/v1/homework-templates",
      params as Record<string, string> | undefined,
    ),
  createHomework: (body: {
    title: string;
    description: string;
    subject_id?: string;
    default_due_days?: number;
    topic_ids?: string[];
    grade_levels?: string[];
  }) => api.post<HomeworkTemplateRow>("/api/v1/homework-templates", body),
  publishHomeworkSchoolWide: (id: string) =>
    api.post<HomeworkTemplateRow>(`/api/v1/homework-templates/${id}/publish-school-wide`),
  instantiateHomework: (id: string, body: { class_id: string; due_date?: string }) =>
    api.post<{ instance_id: string; template_id: string; due_date: string; class_id: string }>(
      `/api/v1/homework-templates/${id}/instantiate`,
      body,
    ),
  syncHomeworkFromTemplate: (homework_id: string) =>
    api.post<{ instance_id: string; synced_at: string }>(
      `/api/v1/homework/${homework_id}/sync-from-template`,
    ),

  listLessonPlan: (params?: { subject_id?: string; published_only?: boolean; mine_only?: boolean }) =>
    api.get<LessonPlanTemplateRow[]>(
      "/api/v1/lesson-plan-templates",
      params as Record<string, string> | undefined,
    ),
  createLessonPlan: (body: {
    title: string;
    objectives?: string;
    activities?: string;
    resources?: string;
    subject_id?: string;
    suggested_period_number?: number;
    topic_ids?: string[];
    grade_levels?: string[];
  }) => api.post<LessonPlanTemplateRow>("/api/v1/lesson-plan-templates", body),
  publishLessonPlanSchoolWide: (id: string) =>
    api.post<LessonPlanTemplateRow>(`/api/v1/lesson-plan-templates/${id}/publish-school-wide`),
  instantiateLessonPlan: (id: string, body: { class_id: string; scheduled_date?: string; scheduled_period_number?: number }) =>
    api.post<{ instance_id: string; template_id: string; class_id: string }>(
      `/api/v1/lesson-plan-templates/${id}/instantiate`,
      body,
    ),
};
