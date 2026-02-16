-- Add message column to existing free_trial_requests table
-- Run this if you already created the table without the message field
-- For SQLite
ALTER TABLE free_trial_requests
ADD COLUMN message TEXT NULL;
-- Verify the column was added
PRAGMA table_info(free_trial_requests);
-- Optional: Check existing records
SELECT id,
    username,
    email,
    message
FROM free_trial_requests
LIMIT 5;