// Same rule as the server (core/hashing.py): 5 to 16 digits once spaces and dashes are dropped.
const USC_PATTERN = /^\d{5,16}$/;

/** People type a service number with spaces or dashes; the server wants digits only. */
export const bareUsc = (value: string) => value.replace(/[\s-]/g, '');

/** True when the typed value could be a service number. Empty is not checked here. */
export const uscShapeOk = (value: string) => USC_PATTERN.test(bareUsc(value));

export const USC_HINT = 'A service number is 5 to 16 digits.';
