/** POST /api/bills/by-usc/start (202). The same body whether or not the service number exists. */
export interface UscStarted {
  status: 'accepted';
  message: string;
  expires_in_seconds: number;
  /** False only on a development server: no code is sent, and verify is called without one. */
  code_required: boolean;
}

export interface UscRequest {
  discom: string;
  service_number: string;
}
