import type { Job, Recipe } from './types';
export const REVISION: string;
export const RECIPE_ID: string;
export function terminal(status: string): boolean;
export function statusText(status: string): string;
export function validateRecipe(value: unknown): Recipe;
export function validateReplay(value: unknown): Job;
export function recipeLink(recipe: Recipe, base: string): string;
export function recipeFromHash(hash: string): Recipe | null;
export function readStored<T>(key: string, validate: (value: unknown) => T, limit?: number): T[];

export type ActivationRecipe = { id: string; name: string; description: string; components: [number, number, number][]; source?: string; note?: string };
export const ACTIVATION_RECIPES: ActivationRecipe[];
export function activationRecipe(id: string): ActivationRecipe;
