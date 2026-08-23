/** Matches core/exceptions.py's error envelope: {"error": {code, message, details}}. */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
