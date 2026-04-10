ALTER TABLE user_feedback
  ADD COLUMN IF NOT EXISTS feedback_type TEXT NOT NULL DEFAULT 'general';

ALTER TABLE user_feedback
  ADD COLUMN IF NOT EXISTS conversation_id TEXT;

ALTER TABLE user_feedback
  ADD COLUMN IF NOT EXISTS message_index INTEGER;
