const SETTINGS = {
  spreadsheetId: '18T-uYZh9EF1MWIYYSMZyEhFxIzZXKfA63O10qrXRjzw',
  sheetName: 'Enquiries',
  notifyEmail: 'rajiv.gupta@digisciencetechsol.com',
  timezone: 'Asia/Kolkata'
};

function doGet() {
  return ContentService
    .createTextOutput(JSON.stringify({ ok: true, message: 'DigiScience enquiry endpoint is live.' }))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  try {
    const data = normalizePayload_(e);

    if (data.website) {
      return jsonResponse_({ ok: true, skipped: true });
    }

    if (!data.name || !data.email || !data.message) {
      throw new Error('Name, email, and requirement are required.');
    }

    if (!isValidEmail_(data.email)) {
      throw new Error('Invalid email address.');
    }

    const sheet = getSheet_();
    const leadId = Utilities.getUuid().split('-')[0].toUpperCase();
    const timestamp = Utilities.formatDate(new Date(), SETTINGS.timezone, 'yyyy-MM-dd HH:mm:ss');

    sheet.appendRow([
      timestamp,
      leadId,
      data.name,
      data.email,
      data.company || '',
      data.service || 'General enquiry',
      data.message,
      data.source || '',
      data.submittedAt || ''
    ]);

    notifyByEmail_(leadId, timestamp, data);

    return jsonResponse_({ ok: true, leadId: leadId });
  } catch (error) {
    return jsonResponse_({ ok: false, error: String(error && error.message ? error.message : error) });
  }
}

function normalizePayload_(e) {
  const params = e && e.parameter ? e.parameter : {};
  return {
    name: String(params.name || '').trim(),
    email: String(params.email || '').trim(),
    company: String(params.company || '').trim(),
    service: String(params.service || 'General enquiry').trim(),
    message: String(params.message || '').trim(),
    website: String(params.website || '').trim(),
    source: String(params.source || '').trim(),
    submittedAt: String(params.submittedAt || '').trim()
  };
}

function isValidEmail_(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function getSheet_() {
  const spreadsheet = SpreadsheetApp.openById(SETTINGS.spreadsheetId);
  let sheet = spreadsheet.getSheetByName(SETTINGS.sheetName);

  if (!sheet) {
    sheet = spreadsheet.insertSheet(SETTINGS.sheetName);
    sheet.appendRow(['Timestamp', 'Lead ID', 'Name', 'Email', 'Company', 'Service', 'Requirement', 'Source', 'Submitted At']);
    sheet.setFrozenRows(1);
  }

  return sheet;
}

function notifyByEmail_(leadId, timestamp, data) {
  if (!SETTINGS.notifyEmail) return;

  const subject = 'New website enquiry - ' + (data.service || 'General enquiry');
  const htmlBody = [
    '<div style="font-family:Arial,sans-serif;line-height:1.6;color:#111">',
    '<h2 style="margin:0 0 12px">New website enquiry</h2>',
    '<p style="margin:0 0 16px">A new enquiry has been captured from the DigiScience website.</p>',
    '<table cellpadding="8" cellspacing="0" border="1" style="border-collapse:collapse;border-color:#d9e2f1">',
    '<tr><td><strong>Lead ID</strong></td><td>' + escapeHtml_(leadId) + '</td></tr>',
    '<tr><td><strong>Timestamp</strong></td><td>' + escapeHtml_(timestamp) + '</td></tr>',
    '<tr><td><strong>Name</strong></td><td>' + escapeHtml_(data.name) + '</td></tr>',
    '<tr><td><strong>Email</strong></td><td>' + escapeHtml_(data.email) + '</td></tr>',
    '<tr><td><strong>Company</strong></td><td>' + escapeHtml_(data.company || '-') + '</td></tr>',
    '<tr><td><strong>Service</strong></td><td>' + escapeHtml_(data.service || '-') + '</td></tr>',
    '<tr><td><strong>Requirement</strong></td><td>' + escapeHtml_(data.message).replace(/\r?\n/g, '<br>') + '</td></tr>',
    '<tr><td><strong>Source</strong></td><td>' + escapeHtml_(data.source || '-') + '</td></tr>',
    '</table>',
    '<p style="margin-top:16px">This enquiry was also stored in Google Sheets.</p>',
    '</div>'
  ].join('');

  MailApp.sendEmail({
    to: SETTINGS.notifyEmail,
    subject: subject,
    htmlBody: htmlBody,
    replyTo: data.email,
    name: 'DigiScience Website'
  });
}

function escapeHtml_(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function jsonResponse_(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
