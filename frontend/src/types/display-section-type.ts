export interface DisplaySectionType {
  section_id: string;
  name: string;
  description: string | null;
  sort_order: number;
}

export interface CreateDisplaySectionType {
  name: string;
  description?: string | null;
  sort_order?: number;
}

export interface UpdateDisplaySectionType {
  name?: string;
  description?: string | null;
  sort_order?: number;
}
