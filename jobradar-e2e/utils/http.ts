/** HTTP status codes the jobradar contract uses. Single source for assertions. */
export enum HttpStatus {
  Ok = 200,
  SeeOther = 303,
  BadRequest = 400,
  Forbidden = 403,
  NotFound = 404,
  MethodNotAllowed = 405,
  ServiceUnavailable = 503,
}
