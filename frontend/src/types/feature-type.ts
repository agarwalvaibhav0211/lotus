import { DisplaySectionType } from "./display-section-type";

export interface FeatureType {
  feature_id: string;
  feature_name: string;
  feature_description: string;
  display_section: DisplaySectionType | null;
  display_order: number;
}

export interface CreateFeatureType {
  feature_name: string;
  feature_description: string;
  display_section_id?: string | null;
  display_order?: number;
}

export interface UpdateFeatureType {
  feature_name?: string;
  feature_description?: string;
  display_section_id?: string | null;
  display_order?: number;
}
