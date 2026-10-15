export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type Discom = 'TGSPDCL' | 'TGNPDCL';
export const DISCOMS: Discom[] = ['TGSPDCL', 'TGNPDCL'];
