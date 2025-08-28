import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import nodemailer from 'nodemailer';
import { google } from 'googleapis';
import fetch from 'node-fetch';
import AbortControllerPkg from 'abort-controller';

if (typeof global.AbortController === 'undefined') {
  global.AbortController = AbortControllerPkg;
}

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

// Simple request logger
app.use((req, _res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
  next();
});

const PORT = process.env.PORT || 3000;
const ENGINE_URL = process.env.ENGINE_URL || 'http://localhost:5000';

// In-memory session with default values
let session = {
  id: Date.now().toString(),
  recruiterEmail: process.env.GMAIL_FROM,
  candidateEmail: "doejohn4279@gmail.com",
  status: 'initialized',
  history: [],
};

// Google OAuth2 client (for Gmail + Calendar)
const {
  GOOGLE_CLIENT_ID,
  GOOGLE_CLIENT_SECRET,
  GOOGLE_REFRESH_TOKEN,
  GOOGLE_REDIRECT_URI = 'https://developers.google.com/oauthplayground',
  GMAIL_FROM,
  GOOGLE_CALENDAR_ID = 'primary',
} = process.env;

const oauth2Client = new google.auth.OAuth2(
  GOOGLE_CLIENT_ID,
  GOOGLE_CLIENT_SECRET,
  GOOGLE_REDIRECT_URI
);
oauth2Client.setCredentials({ refresh_token: GOOGLE_REFRESH_TOKEN });

// Gmail transporter using OAuth2
async function createGmailTransporter() {
  const { token } = await oauth2Client.getAccessToken();
  return nodemailer.createTransport({
    service: 'gmail',
    auth: {
      type: 'OAuth2',
      user: GMAIL_FROM,
      clientId: GOOGLE_CLIENT_ID,
      clientSecret: GOOGLE_CLIENT_SECRET,
      refreshToken: GOOGLE_REFRESH_TOKEN,
      accessToken: token,
    },
  });
}

// Google Calendar client
const calendar = google.calendar({ version: 'v3', auth: oauth2Client });

// Gmail API client
const gmail = google.gmail({ version: 'v1', auth: oauth2Client });

// Health
app.get('/', (_req, res) => {
  res.json({ status: 'ok' });
});

// Start session
app.post('/start', async (req, res) => {
  console.log('[/start] Incoming body:', req.body);
  const { recruiterEmail, candidateEmail } = req.body;
  const effectiveRecruiterEmail = recruiterEmail || GMAIL_FROM;
  const effectiveCandidateEmail = candidateEmail || session?.candidateEmail || "doejohn4279@gmail.com";
  console.log('[/start] Effective recruiterEmail:', effectiveRecruiterEmail);
  console.log('[/start] Candidate email:', effectiveCandidateEmail);
  console.log('[/start] ENGINE_URL:', ENGINE_URL);

  if (!effectiveRecruiterEmail || !effectiveCandidateEmail) {
    console.error('[/start] Missing required emails.');
    return res.status(400).json({ error: 'candidateEmail is required; recruiterEmail will default to GMAIL_FROM if not provided' });
  }
  
  // Update existing session or create new one
  session = {
    id: session?.id || Date.now().toString(),
    recruiterEmail: effectiveRecruiterEmail,
    candidateEmail: effectiveCandidateEmail,
    status: 'started',
    history: session?.history || [],
  };

  // Call engine kickoff endpoint with timeout
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => {
      controller.abort();
      console.error('[/start] Engine kickoff request timed out');
    }, 5000);

    console.log('[/start] Notifying engine /kickoff...');
    const response = await fetch(`${ENGINE_URL}/kickoff`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recruiterEmail: effectiveRecruiterEmail, candidateEmail: effectiveCandidateEmail }),
      signal: controller.signal,
    }).catch((err) => {
      console.error('[/start] Engine fetch error:', err?.message || err);
      throw err;
    });

    clearTimeout(timeout);

    if (!response) {
      console.warn('[/start] No response object from fetch (engine might be down).');
    } else if (!response.ok) {
      const text = await response.text().catch(() => '');
      console.error('[/start] Engine kickoff failed. Status:', response.status, 'Body:', text);
    } else {
      console.log('[/start] Engine kickoff acknowledged with status:', response.status);
      
      // Automatically start email polling after successful engine kickoff
      console.log('[/start] Starting email polling automatically...');
      try {
        await stopEmailPolling(); // Stop any existing polling first
        await runPollLoop(7000); // Start with 30 second interval
        console.log('[/start] Email polling started successfully');
      } catch (pollingError) {
        console.error('[/start] Failed to start email polling:', pollingError?.message || pollingError);
      }
    }
  } catch (err) {
    console.error('[/start] Failed to reach engine:', err?.message || err);
  }

  console.log('[/start] Responding to client with session id:', session.id);
  res.json({ message: 'Process started; engine notified to kickoff; email polling started', session });
});

// Gmail polling helpers
let polling = false;
let pollTimer = null;

// Helper function to mark a message as read
async function markMessageAsRead(messageId) {
  try {
    await gmail.users.messages.modify({
      userId: 'me',
      id: messageId,
      requestBody: {
        removeLabelIds: ['UNREAD']
      }
    });
    console.log(`[Polling] Marked message ${messageId} as read`);
  } catch (error) {
    console.error(`[Polling] Failed to mark message ${messageId} as read:`, error?.message || error);
  }
}

function gmailQuery(candidateEmail, label) {
  const filters = [];
  if (candidateEmail) filters.push(`from:${candidateEmail}`);
  // if (label) filters.push(`label:${label}`);
  filters.push('in:inbox');
  filters.push('is:unread');
  return filters.join(' ');
}

function extractPlainText(payload) {
  if (!payload) return '';
  const parts = [];
  const stack = [payload];
  while (stack.length) {
    const node = stack.pop();
    if (!node) continue;
    if (node.mimeType === 'text/plain' && node.body?.data) {
      parts.push(Buffer.from(node.body.data.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'));
    }
    if (Array.isArray(node.parts)) {
      for (const p of node.parts) stack.push(p);
    }
  }
  return parts.join('\n').trim();
}

async function fetchUnreadMessagesOnce(candidateEmail, label) {
  const q = gmailQuery(candidateEmail, label);
  const list = await gmail.users.messages.list({ userId: 'me', q, maxResults: 5 });
  const messages = list.data.messages || [];
  const results = [];
  for (const m of messages) {
    const full = await gmail.users.messages.get({ userId: 'me', id: m.id, format: 'full' });
    const env = full.data?.payload?.headers || [];
    const subj = env.find(h => h.name.toLowerCase() === 'subject')?.value || '';
    const from = env.find(h => h.name.toLowerCase() === 'from')?.value || '';
    const plain = extractPlainText(full.data?.payload) || full.data?.snippet || '';
    results.push({ id: m.id, subject: subj, from, body: plain });
  }
  return results;
}

async function runPollLoop(intervalMs, label) {
  if (polling) return;
  polling = true;
  const candidateEmail = session?.candidateEmail;
  console.log(`[Polling] started intervalMs=${intervalMs} label=${label} candidate=${candidateEmail}`);
  const tick = async () => {
    if (!polling) return;
    try {
      const messages = await fetchUnreadMessagesOnce(candidateEmail, label);
      console.log(`[Polling] Found ${messages.length} new messages`, candidateEmail);
      for (const msg of messages) {
        console.log(`[Polling] New message from ${msg.from}: ${msg.subject}`);
        if (session) session.history.push({ type: 'email_received', from: msg.from, subject: msg.subject, body: msg.body, at: new Date().toISOString() });
        try {
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 5000);
          const response = await fetch(`${ENGINE_URL}/ingestEmail`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ from: msg.from, subject: msg.subject, body: msg.body, sessionId: session?.id }),
            signal: controller.signal,
          });
          clearTimeout(timeout);
          
          // If engine successfully processed the email, mark it as read
          if (response && response.ok) {
            console.log(`[Polling] Engine successfully processed message ${msg.id}, marking as read`);
            await markMessageAsRead(msg.id);
          } else {
            console.warn(`[Polling] Engine failed to process message ${msg.id}, keeping as unread for retry`);
          }
        } catch (e) {
          console.error('[Polling] Forward to engine failed:', e?.message || e);
          // Don't mark as read if there was an error - keep it unread for retry
        }
      }
    } catch (e) {
      console.error('[Polling] tick error:', e?.message || e);
    } finally {
      if (polling) pollTimer = setTimeout(tick, intervalMs);
    }
  };
  tick();
}

async function stopEmailPolling() {
  polling = false;
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
  console.log('[Polling] stopped');
}

// Polling control endpoints
app.post('/emailPolling/start', async (req, res) => {
  try {
    const { intervalMs = 10000, label } = req.body || {};
    await stopEmailPolling();
    await runPollLoop(Number(intervalMs), label);
    res.json({ status: 'polling', intervalMs: Number(intervalMs), label: label || null });
  } catch (e) {
    console.error('[/emailPolling/start] error:', e?.message || e);
    res.status(500).json({ error: 'failed to start polling' });
  }
});

app.post('/emailPolling/stop', async (_req, res) => {
  try {
    await stopEmailPolling();
    res.json({ status: 'stopped' });
  } catch (e) {
    console.error('[/emailPolling/stop] error:', e?.message || e);
    res.status(500).json({ error: 'failed to stop polling' });
  }
});

// Reset session
app.post('/reset', (_req, res) => {
  session = {
    id: Date.now().toString(),
    recruiterEmail: GMAIL_FROM,
    candidateEmail: "doejohn4279@gmail.com",
    status: 'initialized',
    history: [],
  };
  stopEmailPolling().catch(() => {});
  res.json({ message: 'Process reset' });
});

// Status
app.get('/status', (_req, res) => {
  res.json({ status: session.status, session });
});

// Recruiter availability using Google Calendar FreeBusy within Mon-Fri 09:00-17:00 UTC
app.get('/recruiterSlots', async (req, res) => {
  try {
    const { start, end, durationMinutes, calendarId } = req.query;

    const durationMs = Math.max(15, parseInt(durationMinutes || '60', 10)) * 60 * 1000;
    const calId = String(calendarId || GOOGLE_CALENDAR_ID || 'primary');

    const startDate = start ? new Date(String(start)) : new Date();
    const endDate = end ? new Date(String(end)) : new Date(startDate.getTime() + 14 * 24 * 60 * 60 * 1000);

    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
      return res.status(400).json({ error: 'Invalid start or end date' });
    }
    if (endDate <= startDate) {
      return res.status(400).json({ error: 'end must be after start' });
    }

    // Query Google Calendar freebusy
    const fb = await calendar.freebusy.query({
      requestBody: {
        timeMin: startDate.toISOString(),
        timeMax: endDate.toISOString(),
        items: [{ id: calId }],
      },
    });

    const busyWindows = (fb.data?.calendars?.[calId]?.busy || []).map((b) => ({
      start: new Date(b.start),
      end: new Date(b.end),
    }));

    const WORK_START_HOUR = 9; // 09:00 UTC
    const WORK_END_HOUR = 17; // 17:00 UTC
    const LUNCH_START_HOUR = 13; // 13:00 UTC
    const LUNCH_END_HOUR = 14; // 14:00 UTC

    function overlaps(aStart, aEnd, bStart, bEnd) {
      return aStart < bEnd && aEnd > bStart;
    }

    function overlapsBusy(slotStart, slotEnd) {
      for (const w of busyWindows) {
        if (overlaps(slotStart, slotEnd, w.start, w.end)) return true;
      }
      return false;
    }

    const slots = [];
    const cursor = new Date(Date.UTC(startDate.getUTCFullYear(), startDate.getUTCMonth(), startDate.getUTCDate()));

    while (cursor < endDate) {
      const day = cursor.getUTCDay(); // 0 Sun..6 Sat
      const isWeekday = day >= 1 && day <= 5;
      if (isWeekday) {
        const dayStart = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth(), cursor.getUTCDate(), WORK_START_HOUR, 0, 0));
        const dayEnd = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth(), cursor.getUTCDate(), WORK_END_HOUR, 0, 0));
        const lunchStart = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth(), cursor.getUTCDate(), LUNCH_START_HOUR, 0, 0));
        const lunchEnd = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth(), cursor.getUTCDate(), LUNCH_END_HOUR, 0, 0));

        let slotStart = new Date(Math.max(dayStart.getTime(), startDate.getTime()));
        while (true) {
          const slotEnd = new Date(slotStart.getTime() + durationMs);
          if (slotEnd > dayEnd || slotEnd > endDate) break;
          const overlapsLunch = overlaps(slotStart, slotEnd, lunchStart, lunchEnd);
          if (!overlapsLunch && !overlapsBusy(slotStart, slotEnd)) {
            slots.push({ startTime: slotStart.toISOString(), endTime: slotEnd.toISOString() });
          }
          slotStart = new Date(slotStart.getTime() + durationMs);
        }
      }
      cursor.setUTCDate(cursor.getUTCDate() + 1);
    }

    res.json({ slots, window: { start: startDate.toISOString(), end: endDate.toISOString() }, durationMinutes: durationMs / (60 * 1000), calendarId: calId, busy: busyWindows.map(w => ({ start: w.start.toISOString(), end: w.end.toISOString() })) });
  } catch (err) {
    console.error('[/recruiterSlots] error:', err?.response?.data || err?.message || err);
    res.status(500).json({ error: 'failed to compute slots from calendar' });
  }
});

// Send email via Gmail
app.post('/sendEmail', async (req, res) => {
  const { to, subject, body } = req.body;
  if (!to || !subject || !body) {
    return res.status(400).json({ error: 'to, subject, and body are required' });
  }
  try {
    const transporter = await createGmailTransporter();
    await transporter.sendMail({
      from: GMAIL_FROM,
      to,
      subject,
      text: body,
    });
    if (session) session.history.push({ type: 'email_sent', to, subject, body, at: new Date().toISOString() });
    res.json({ status: 'sent' });
  } catch (error) {
    console.error('Gmail send error:', error?.response?.data || error?.message || error);
    res.status(500).json({ error: 'Failed to send email' });
  }
});

// Receive email (simulate)
app.post('/receiveEmail', async (req, res) => {
  const { from, subject, body } = req.body;
  if (session) session.history.push({ type: 'email_received', from, subject, body, at: new Date().toISOString() });
  console.log(`[/receiveEmail] Received email from ${from}: ${subject} - ${body}`);

  // Forward to engine for parsing/next actions
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => {
      controller.abort();
      console.error('[/receiveEmail] Engine ingestEmail request timed out');
    }, 5000);

    console.log('[/receiveEmail] Forwarding to engine /ingestEmail...');
    const response = await fetch(`${ENGINE_URL}/ingestEmail`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, subject, body, sessionId: session?.id }),
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      console.error('[/receiveEmail] Engine ingestEmail failed. Status:', response.status, 'Body:', text);
    } else {
      console.log('[/receiveEmail] Engine ingestEmail acknowledged with status:', response.status);
    }
  } catch (err) {
    console.error('[/receiveEmail] Failed to reach engine ingestEmail:', err?.message || err);
  }

  res.json({ status: 'received' });
});

// Create calendar event via Google Calendar AND send invite to candidate
app.post('/createEvent', async (req, res) => {
  const { startTime, endTime, subject, location } = req.body;
  if (!startTime || !endTime || !subject) {
    return res.status(400).json({ error: 'startTime, endTime, and subject are required' });
  }

  try {
    // Pull candidate + recruiter emails from session
    const recruiterEmail = session?.recruiterEmail || GMAIL_FROM;
    const candidateEmail = session?.candidateEmail;

    if (!candidateEmail) {
      return res.status(400).json({ error: 'Candidate email not available' });
    }

    // Create event with attendees
    const response = await calendar.events.insert({
      calendarId: GOOGLE_CALENDAR_ID || 'primary',
      sendUpdates: 'all', // ensures Google emails the invite to attendees
      requestBody: {
        summary: subject,
        start: { dateTime: startTime, timeZone: 'UTC' },
        end: { dateTime: endTime, timeZone: 'UTC' },
        location: location || 'Virtual Interview',
        attendees: [
          { email: recruiterEmail }, // recruiter (organizer)
          { email: candidateEmail }, // candidate (invitee)
        ],
      },
    });

    const eventId = response.data?.id;

    if (session) {
      session.history.push({
        type: 'event_created',
        eventId,
        recruiterEmail,
        candidateEmail,
        at: new Date().toISOString(),
      });
    }

    res.json({ status: 'event created & invite sent', eventId });
  } catch (error) {
    console.error('Google Calendar error:', error?.response?.data || error?.message || error);
    res.status(500).json({ error: 'Failed to create event & send invite' });
  }
});


app.listen(PORT, () => {
  console.log(`Backend server running at http://localhost:${PORT}`);
});
