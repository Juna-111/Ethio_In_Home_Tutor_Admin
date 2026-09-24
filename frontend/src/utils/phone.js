/**
 * Normalizes Ethiopian phone numbers from various common user formats to canonical E.164 (+251XXXXXXXXX).
 *
 * Supported inputs:
 *  - 0911223344 -> +251911223344
 *  - 0711223344 -> +251711223344
 *  - 911223344  -> +251911223344
 *  - 711223344  -> +251711223344
 *  - 251911223344 -> +251911223344
 *  - +251 91 122 3344 -> +251911223344
 *
 * Returns normalized string "+251XXXXXXXXX" or null if invalid.
 */
export function normalizeEthiopianPhone(input) {
  if (!input || typeof input !== 'string') return null;

  // Strip all non-digit and non-plus characters
  const clean = input.replace(/[\s\-()]/g, '');

  // Handle +251 prefix
  if (clean.startsWith('+251')) {
    const digits = clean.slice(4);
    if (/^[79]\d{8}$/.test(digits)) {
      return `+251${digits}`;
    }
    return null;
  }

  // Handle 251 without plus
  if (clean.startsWith('251')) {
    const digits = clean.slice(3);
    if (/^[79]\d{8}$/.test(digits)) {
      return `+251${digits}`;
    }
    return null;
  }

  // Handle local 09... or 07...
  if (clean.startsWith('0')) {
    const digits = clean.slice(1);
    if (/^[79]\d{8}$/.test(digits)) {
      return `+251${digits}`;
    }
    return null;
  }

  // Handle 9... or 7... (9 digits directly)
  if (/^[79]\d{8}$/.test(clean)) {
    return `+251${clean}`;
  }

  return null;
}

export function isValidEthiopianPhone(input) {
  return normalizeEthiopianPhone(input) !== null;
}
