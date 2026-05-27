/**
 * Phase 16f — Question Bank browse + submit-draft.
 *
 * Teachers see every published question for their school, filter by
 * subject / type / difficulty, and submit a new draft for HoD
 * approval.
 */
"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  curriculumApi,
  questionBankApi,
  type SchoolSubject,
  type QuestionRow,
  type QuestionType,
} from "@/lib/curriculum-api";
import {
  Card, CardHeader, CardTitle, CardContent,
  Button, Input, Alert, AlertTitle, AlertDescription, Badge,
} from "@eduzim/ui";

const DIFFICULTY_LABELS = ["", "Easy", "2", "Medium", "4", "Hard"];

export default function QuestionBankPage() {
  const [subjects, setSubjects] = useState<SchoolSubject[]>([]);
  const [questions, setQuestions] = useState<QuestionRow[]>([]);
  const [filterSubject, setFilterSubject] = useState<string>("");
  const [filterType, setFilterType] = useState<QuestionType | "">("");
  const [filterDifficulty, setFilterDifficulty] = useState<number | "">("");
  const [loading, setLoading] = useState(true);
  const [showSubmitForm, setShowSubmitForm] = useState(false);

  useEffect(() => {
    curriculumApi.listSubjects().then((r) => setSubjects(r.data));
  }, []);

  const load = () => {
    setLoading(true);
    const params: Record<string, any> = {};
    if (filterSubject) params.subject_id = filterSubject;
    if (filterType) params.question_type = filterType;
    if (filterDifficulty) params.difficulty = filterDifficulty;
    questionBankApi
      .list(params)
      .then((r) => setQuestions(r.data))
      .finally(() => setLoading(false));
  };

  useEffect(load, [filterSubject, filterType, filterDifficulty]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Question bank</h1>
          <p className="text-sm text-muted-foreground">
            Reusable questions across your school. Submit a new draft;
            the HoD reviews + approves before it's published.{" "}
            <Link href="/question-bank/drafts" className="text-primary hover:underline">
              Review queue →
            </Link>
          </p>
        </div>
        <Button onClick={() => setShowSubmitForm((x) => !x)}>
          {showSubmitForm ? "Cancel" : "Submit a question"}
        </Button>
      </div>

      {showSubmitForm && subjects.length > 0 && (
        <SubmitDraftForm
          subjects={subjects}
          onSubmitted={() => {
            setShowSubmitForm(false);
            load();
          }}
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-3">
            <select
              value={filterSubject}
              onChange={(e) => setFilterSubject(e.target.value)}
              className="rounded border bg-background px-2 py-1.5 text-sm"
            >
              <option value="">All subjects</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <select
              value={filterType}
              onChange={(e) => setFilterType((e.target.value || "") as any)}
              className="rounded border bg-background px-2 py-1.5 text-sm"
            >
              <option value="">All types</option>
              <option value="MCQ">MCQ</option>
              <option value="TRUE_FALSE">True / False</option>
              <option value="SHORT_ANSWER">Short answer</option>
            </select>
            <select
              value={filterDifficulty}
              onChange={(e) => setFilterDifficulty(e.target.value ? parseInt(e.target.value, 10) : "")}
              className="rounded border bg-background px-2 py-1.5 text-sm"
            >
              <option value="">All difficulty</option>
              {[1, 2, 3, 4, 5].map((d) => (
                <option key={d} value={d}>{DIFFICULTY_LABELS[d]}</option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="h-48 animate-pulse rounded bg-muted" />
      ) : questions.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No questions yet for this filter. Submit one to start the
            bank.
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-3">
          {questions.map((q) => (
            <li key={q.id}>
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge>{q.question_type}</Badge>
                    <Badge variant="outline">Difficulty {q.difficulty}</Badge>
                    {q.attempts_count > 0 && (
                      <span className="text-xs text-muted-foreground">
                        {q.correct_count}/{q.attempts_count} correct
                      </span>
                    )}
                  </div>
                  <div className="text-sm font-medium mb-2">{q.text}</div>
                  {q.options.length > 0 && (
                    <ol className="ml-4 space-y-1">
                      {q.options.map((o) => (
                        <li key={o.id} className="text-sm">
                          <span className="font-mono mr-2">{o.label}.</span>
                          <span className={o.is_correct ? "text-green-700 font-medium" : ""}>
                            {o.text}{o.is_correct && " ✓"}
                          </span>
                        </li>
                      ))}
                    </ol>
                  )}
                  {q.correct_answer_text && q.question_type !== "MCQ" && (
                    <div className="text-xs text-green-700 mt-2">
                      Answer: {q.correct_answer_text}
                    </div>
                  )}
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface SubmitDraftFormProps {
  subjects: SchoolSubject[];
  onSubmitted: () => void;
}

function SubmitDraftForm({ subjects, onSubmitted }: SubmitDraftFormProps) {
  const [subjectId, setSubjectId] = useState(subjects[0]?.id ?? "");
  const [qType, setQType] = useState<QuestionType>("MCQ");
  const [text, setText] = useState("");
  const [difficulty, setDifficulty] = useState(3);
  const [correctAnswer, setCorrectAnswer] = useState("");
  const [options, setOptions] = useState([
    { label: "A", text: "", is_correct: false },
    { label: "B", text: "", is_correct: false },
  ]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const body: any = {
        subject_id: subjectId,
        question_type: qType,
        text,
        difficulty,
      };
      if (qType === "MCQ") {
        body.options = options.filter((o) => o.text.trim());
      } else {
        body.correct_answer_text = correctAnswer;
      }
      await questionBankApi.submitDraft(body);
      onSubmitted();
    } catch (e: any) {
      setError(e?.detail ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Submit a draft</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Could not submit</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <div className="grid gap-3 md:grid-cols-3">
          <select
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
            className="rounded border bg-background px-2 py-1.5 text-sm"
          >
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <select
            value={qType}
            onChange={(e) => setQType(e.target.value as QuestionType)}
            className="rounded border bg-background px-2 py-1.5 text-sm"
          >
            <option value="MCQ">MCQ</option>
            <option value="TRUE_FALSE">True / False</option>
            <option value="SHORT_ANSWER">Short answer</option>
          </select>
          <select
            value={difficulty}
            onChange={(e) => setDifficulty(parseInt(e.target.value, 10))}
            className="rounded border bg-background px-2 py-1.5 text-sm"
          >
            {[1, 2, 3, 4, 5].map((d) => (
              <option key={d} value={d}>Difficulty {d}</option>
            ))}
          </select>
        </div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Question text"
          rows={3}
          className="w-full rounded border bg-background p-2 text-sm"
        />
        {qType === "MCQ" ? (
          <div className="space-y-2">
            {options.map((o, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span className="font-mono text-sm w-6">{o.label}.</span>
                <Input
                  value={o.text}
                  onChange={(e) => {
                    const next = [...options];
                    next[idx] = { ...next[idx], text: e.target.value };
                    setOptions(next);
                  }}
                  placeholder={`Option ${o.label}`}
                />
                <label className="text-xs flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={o.is_correct}
                    onChange={(e) => {
                      const next = [...options];
                      next[idx] = { ...next[idx], is_correct: e.target.checked };
                      setOptions(next);
                    }}
                  />
                  correct
                </label>
              </div>
            ))}
            {options.length < 6 && (
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  setOptions([
                    ...options,
                    {
                      label: String.fromCharCode(65 + options.length),
                      text: "",
                      is_correct: false,
                    },
                  ])
                }
              >
                + Add option
              </Button>
            )}
          </div>
        ) : (
          <Input
            value={correctAnswer}
            onChange={(e) => setCorrectAnswer(e.target.value)}
            placeholder={qType === "TRUE_FALSE" ? "true or false" : "Expected answer"}
          />
        )}
        <Button onClick={submit} disabled={busy || !text.trim()}>
          {busy ? "Submitting…" : "Submit for HoD review"}
        </Button>
      </CardContent>
    </Card>
  );
}
