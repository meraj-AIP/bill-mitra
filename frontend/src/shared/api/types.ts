export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type Discom = 'TGSPDCL' | 'TGNPDCL';
export const DISCOMS: Discom[] = ['TGSPDCL', 'TGNPDCL'];

export type UnitKind = 'discom' | 'circle' | 'division' | 'subdivision' | 'section' | 'ero';

export interface Unit {
  id: string;
  kind: UnitKind;
  name: string;
  code: string | null;
  discom: Discom;
  parent_id: string | null;
  /** A section may point at the ERO that bills it. */
  ero_id: string | null;
  aliases: string[];
  active: boolean;
  children_count: number;
}

/** The part of a unit a picker needs; an account scope has the same shape. */
export interface UnitRef {
  unit_id: string;
  name: string;
  kind: UnitKind;
}

export const UNIT_KIND_LABEL: Record<UnitKind, string> = {
  discom: 'DISCOM', circle: 'Circle', division: 'Division', subdivision: 'Sub-division', section: 'Section', ero: 'ERO',
};
