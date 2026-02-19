/**
 * Convert a 24-hour time string like "14:05" to "2:05 PM".
 * If already looks 12-hour with AM/PM, it will be returned as-is.
 */
export function formatToAmPm(time: string | null | undefined): string {
  if (!time) return "";
  const t = String(time).trim();
  // If already contains AM/PM, assume it's fine
  if (/am|pm/i.test(t))
    return t.toUpperCase().replace("am", "AM").replace("pm", "PM");
  const m = t.match(/^(\d{1,2}):(\d{2})$/);
  if (!m) return t; // unknown format
  let h = parseInt(m[1], 10);
  const mm = m[2];
  const suffix = h >= 12 ? "PM" : "AM";
  h = h % 12;
  if (h === 0) h = 12;
  return `${h}:${mm} ${suffix}`;
}

/**
 * Parse a time string (either 24-hour "14:05" or 12-hour "2:05 PM") 
 * and return total minutes from midnight for sorting purposes.
 */
export function parseTimeToMinutes(time: string | null | undefined): number {
  if (!time) return 0;
  const t = String(time).trim().toUpperCase();
  
  // Check if it's 12-hour format with AM/PM
  const ampmMatch = t.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
  if (ampmMatch) {
    let h = parseInt(ampmMatch[1], 10);
    const mm = parseInt(ampmMatch[2], 10);
    const period = ampmMatch[3].toUpperCase();
    
    if (period === "AM" && h === 12) h = 0;
    else if (period === "PM" && h !== 12) h += 12;
    
    return h * 60 + mm;
  }
  
  // Try 24-hour format
  const match24 = t.match(/^(\d{1,2}):(\d{2})$/);
  if (match24) {
    const h = parseInt(match24[1], 10);
    const mm = parseInt(match24[2], 10);
    return h * 60 + mm;
  }
  
  return 0;
}

export function timeRangeToAmPm(
  start?: string | null,
  end?: string | null
): string {
  const s = formatToAmPm(start || "");
  const e = formatToAmPm(end || "");
  if (!s && !e) return "";
  if (!s) return e;
  if (!e) return s;
  return `${s} - ${e}`;
}
