export const VALID_CLASSES = [
  '63TTQL',
  '63HTTT',
  '63CNTT',
  '63LFW',
  '64TTQL',
  '64HTTT',
  '64CNTT',
  '64LFW',
]

export const classMatchesStudentCode = (studentCode, className) => {
  if (!studentCode || !className) return true
  return className.startsWith(studentCode.slice(0, 2))
}
