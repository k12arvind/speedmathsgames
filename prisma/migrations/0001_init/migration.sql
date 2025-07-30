-- Create tables for speedmathsgames (PostgreSQL)
CREATE TABLE "User" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username text UNIQUE NOT NULL,
  displayName text,
  email text UNIQUE,
  oauthProvider text,
  oauthSub text,
  createdAt timestamptz DEFAULT now(),
  updatedAt timestamptz DEFAULT now()
);

CREATE TABLE "Admin" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  userId uuid UNIQUE NOT NULL,
  role text NOT NULL,
  createdAt timestamptz DEFAULT now()
);

CREATE TABLE "GamePreset" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text UNIQUE NOT NULL,
  description text,
  config jsonb NOT NULL,
  createdBy uuid NOT NULL,
  createdAt timestamptz DEFAULT now(),
  updatedAt timestamptz DEFAULT now()
);

CREATE TABLE "TopicConfig" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  topic text NOT NULL,
  isActive boolean DEFAULT true,
  rules jsonb NOT NULL,
  validation jsonb NOT NULL,
  version int DEFAULT 1,
  createdAt timestamptz DEFAULT now(),
  updatedAt timestamptz DEFAULT now()
);

CREATE TABLE "GameSession" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  userId uuid NOT NULL,
  startedAt timestamptz DEFAULT now(),
  endedAt timestamptz,
  timeLimitSec int NOT NULL,
  config jsonb NOT NULL,
  totalQuestions int DEFAULT 0,
  answeredCount int DEFAULT 0,
  correctCount int DEFAULT 0,
  skippedCount int DEFAULT 0,
  score int DEFAULT 0,
  avgTimeMs int DEFAULT 0,
  status text DEFAULT 'active'
);

CREATE TABLE "QuestionInstance" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sessionId uuid NOT NULL REFERENCES "GameSession"(id) ON DELETE CASCADE,
  indexInSession int NOT NULL,
  topic text NOT NULL,
  difficulty text NOT NULL,
  prompt text NOT NULL,
  payload jsonb NOT NULL,
  createdAt timestamptz DEFAULT now()
);
CREATE INDEX "QuestionInstance_session_index" ON "QuestionInstance"(sessionId, indexInSession);

CREATE TABLE "UserResponse" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sessionId uuid NOT NULL REFERENCES "GameSession"(id) ON DELETE CASCADE,
  questionId uuid NOT NULL REFERENCES "QuestionInstance"(id) ON DELETE CASCADE,
  answeredAt timestamptz DEFAULT now(),
  timeTakenMs int NOT NULL,
  userAnswer text NOT NULL,
  normalizedAnswer text,
  isCorrect boolean NOT NULL,
  wasSkipped boolean DEFAULT false
);
CREATE INDEX "UserResponse_session_question_index" ON "UserResponse"(sessionId, questionId);

CREATE TABLE "UserTopicStats" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  userId uuid NOT NULL,
  topic text NOT NULL,
  gamesPlayed int DEFAULT 0,
  totalAnswered int DEFAULT 0,
  totalCorrect int DEFAULT 0,
  avgTimeMs int DEFAULT 0,
  last7Days jsonb NOT NULL DEFAULT '{}'::jsonb,
  updatedAt timestamptz DEFAULT now()
);

CREATE TABLE "Leaderboard" (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scope text NOT NULL,
  topic text NOT NULL,
  entries jsonb NOT NULL,
  validFrom timestamptz NOT NULL,
  validTo timestamptz NOT NULL,
  computedAt timestamptz DEFAULT now()
);

CREATE TABLE "AppSetting" (
  key text PRIMARY KEY,
  val jsonb NOT NULL,
  updatedAt timestamptz DEFAULT now()
);

-- FKs
ALTER TABLE "GameSession"
  ADD CONSTRAINT "GameSession_user_fkey" FOREIGN KEY (userId) REFERENCES "User"(id) ON DELETE CASCADE;
