import { makeAdminResourceHooks } from "@/hooks/useAdminResource";
import type {
  CharacterClassAdminOut,
  EnemyTemplateAdminOut,
  ExpeditionTemplateAdminOut,
  HeroTemplateAdminOut,
  ItemTemplateAdminOut,
  QuestDefinitionAdminOut,
  RaceAdminOut,
} from "@/types";

export type FieldType = "text" | "textarea" | "number" | "checkbox" | "select" | "multiselect" | "race-select" | "class-select";

export interface FieldOption {
  value: string;
  label: string;
}

export interface FieldConfig {
  key: string;
  label: string;
  type: FieldType;
  options?: FieldOption[];
  /** Editable only at creation — rendered read-only/hidden on the edit form.
   * Mirrors rpg-backend's *Update schemas, which simply omit these keys. */
  createOnly?: boolean;
  step?: string;
  defaultValue?: string | number | boolean;
  /** Set when the API's Out schema uses a different field name than the
   * Create/Update payload does for the same data — e.g. items expose
   * `affixes: [{id, stat_type}]` on read but accept `affix_stat_types:
   * string[]` on write. Without this, buildInitialState would look for
   * `existing[field.key]`, find nothing, and silently start the field
   * empty instead of pre-filling it from the real row. */
  sourceKey?: string;
}

export interface ColumnConfig {
  key: string;
  label: string;
}

export interface ResourceConfig {
  key: string;
  label: string;
  basePath: string;
  columns: ColumnConfig[];
  fields: FieldConfig[];
  hooks: ReturnType<typeof makeAdminResourceHooks>;
  /** Only the four resources with a POST {basePath}/{id}/image endpoint
   * (rpg-backend's image_service.py, kind∈{heroes,enemies,items,expeditions}) —
   * races/classes/quests have no upload route, so no widget for them. */
  imageUploadKind?: "heroes" | "enemies" | "items" | "expeditions";
}

const RARITY_OPTIONS: FieldOption[] = [
  { value: "common", label: "Обычная" },
  { value: "rare", label: "Редкая" },
  { value: "epic", label: "Эпическая" },
  { value: "legendary", label: "Легендарная" },
];

const SLOT_OPTIONS: FieldOption[] = [
  "weapon",
  "helmet",
  "armor",
  "boots",
  "gloves",
  "ring",
  "amulet",
].map((v) => ({ value: v, label: v }));

const STAT_TYPE_OPTIONS: FieldOption[] = ["hp", "attack", "defense", "speed"].map((v) => ({ value: v, label: v }));

const CONDITION_TYPE_OPTIONS: FieldOption[] = [
  { value: "battles_won", label: "Побед в боях" },
  { value: "expeditions_claimed", label: "Экспедиций забрано" },
  { value: "chests_opened", label: "Сундуков открыто" },
  { value: "hero_level", label: "Уровень героя" },
  { value: "items_equipped", label: "Предметов экипировано" },
  { value: "skills_upgraded", label: "Улучшений навыков" },
];

export const RESOURCES: Record<string, ResourceConfig> = {
  races: {
    key: "races",
    label: "Расы",
    basePath: "/admin/races",
    columns: [
      { key: "name", label: "Название" },
      { key: "code", label: "Код" },
      { key: "sort_order", label: "Порядок" },
    ],
    fields: [
      { key: "code", label: "Код", type: "text", createOnly: true },
      { key: "name", label: "Название", type: "text" },
      { key: "description", label: "Описание", type: "textarea" },
      { key: "sort_order", label: "Порядок сортировки", type: "number", defaultValue: 0 },
    ],
    hooks: makeAdminResourceHooks<RaceAdminOut, unknown, unknown>("races", "/admin/races"),
  },
  classes: {
    key: "classes",
    label: "Классы",
    basePath: "/admin/classes",
    columns: [
      { key: "name", label: "Название" },
      { key: "code", label: "Код" },
      { key: "base_hp", label: "HP" },
      { key: "base_attack", label: "ATK" },
    ],
    fields: [
      { key: "code", label: "Код", type: "text", createOnly: true },
      { key: "name", label: "Название", type: "text" },
      { key: "description", label: "Описание", type: "textarea" },
      { key: "base_hp", label: "Базовое HP", type: "number" },
      { key: "base_attack", label: "Базовая атака", type: "number" },
      { key: "base_defense", label: "Базовая защита", type: "number" },
      { key: "base_speed", label: "Базовая скорость", type: "number" },
      { key: "base_crit_chance", label: "Шанс крита", type: "number", step: "0.01", defaultValue: 0.05 },
      { key: "base_crit_damage", label: "Урон крита (множитель)", type: "number", step: "0.01", defaultValue: 1.5 },
      { key: "hp_per_level", label: "HP за уровень", type: "number", step: "0.1" },
      { key: "attack_per_level", label: "Атака за уровень", type: "number", step: "0.1" },
      { key: "defense_per_level", label: "Защита за уровень", type: "number", step: "0.1" },
      { key: "speed_per_level", label: "Скорость за уровень", type: "number", step: "0.1" },
      { key: "sort_order", label: "Порядок сортировки", type: "number", defaultValue: 0 },
    ],
    hooks: makeAdminResourceHooks<CharacterClassAdminOut, unknown, unknown>("classes", "/admin/classes"),
  },
  "hero-templates": {
    key: "hero-templates",
    label: "Шаблоны героев",
    basePath: "/admin/hero-templates",
    columns: [
      { key: "name", label: "Имя" },
      { key: "race", label: "Раса" },
      { key: "character_class", label: "Класс" },
    ],
    fields: [
      { key: "race_id", label: "Раса", type: "race-select" },
      { key: "class_id", label: "Класс", type: "class-select" },
      { key: "name", label: "Имя", type: "text" },
      { key: "description", label: "Описание", type: "textarea" },
      { key: "sort_order", label: "Порядок сортировки", type: "number", defaultValue: 0 },
    ],
    hooks: makeAdminResourceHooks<HeroTemplateAdminOut, unknown, unknown>("hero-templates", "/admin/hero-templates"),
    imageUploadKind: "heroes",
  },
  enemies: {
    key: "enemies",
    label: "Враги",
    basePath: "/admin/enemies",
    columns: [
      { key: "name", label: "Имя" },
      { key: "level", label: "Ур." },
      { key: "hp", label: "HP" },
      { key: "reward_coins", label: "Награда" },
    ],
    fields: [
      { key: "name", label: "Имя", type: "text" },
      { key: "description", label: "Описание", type: "textarea" },
      { key: "level", label: "Требуемый уровень героя", type: "number" },
      { key: "hp", label: "HP", type: "number" },
      { key: "attack", label: "Атака", type: "number" },
      { key: "defense", label: "Защита", type: "number" },
      { key: "speed", label: "Скорость", type: "number" },
      { key: "crit_chance", label: "Шанс крита", type: "number", step: "0.01", defaultValue: 0.05 },
      { key: "crit_damage", label: "Урон крита (множитель)", type: "number", step: "0.01", defaultValue: 1.5 },
      { key: "reward_xp", label: "Награда XP", type: "number" },
      { key: "reward_coins", label: "Награда монет", type: "number" },
      { key: "sort_order", label: "Порядок сортировки", type: "number", defaultValue: 0 },
    ],
    hooks: makeAdminResourceHooks<EnemyTemplateAdminOut, unknown, unknown>("enemies", "/admin/enemies"),
    imageUploadKind: "enemies",
  },
  items: {
    key: "items",
    label: "Предметы",
    basePath: "/admin/items",
    columns: [
      { key: "name", label: "Название" },
      { key: "slot", label: "Слот" },
      { key: "tier", label: "Tier" },
      { key: "rarity", label: "Редкость" },
    ],
    fields: [
      { key: "name", label: "Название", type: "text" },
      { key: "description", label: "Описание", type: "textarea" },
      { key: "slot", label: "Слот", type: "select", options: SLOT_OPTIONS, createOnly: true },
      { key: "tier", label: "Tier (1-10)", type: "number", createOnly: true },
      { key: "rarity", label: "Редкость", type: "select", options: RARITY_OPTIONS, createOnly: true },
      {
        key: "affix_stat_types",
        sourceKey: "affixes",
        label: "Доп. характеристики",
        type: "multiselect",
        options: STAT_TYPE_OPTIONS,
      },
      { key: "sort_order", label: "Порядок сортировки", type: "number", defaultValue: 0 },
    ],
    hooks: makeAdminResourceHooks<ItemTemplateAdminOut, unknown, unknown>("items", "/admin/items"),
    imageUploadKind: "items",
  },
  expeditions: {
    key: "expeditions",
    label: "Экспедиции",
    basePath: "/admin/expeditions",
    columns: [
      { key: "name", label: "Название" },
      { key: "duration_seconds", label: "Длительность, с" },
      { key: "required_hero_level", label: "Треб. ур." },
    ],
    fields: [
      { key: "name", label: "Название", type: "text" },
      { key: "description", label: "Описание", type: "textarea" },
      { key: "duration_seconds", label: "Длительность (сек)", type: "number" },
      { key: "required_hero_level", label: "Требуемый уровень героя", type: "number" },
      { key: "reward_xp", label: "Награда XP", type: "number" },
      { key: "reward_coins", label: "Награда монет", type: "number" },
      { key: "sort_order", label: "Порядок сортировки", type: "number", defaultValue: 0 },
    ],
    hooks: makeAdminResourceHooks<ExpeditionTemplateAdminOut, unknown, unknown>("expeditions", "/admin/expeditions"),
    imageUploadKind: "expeditions",
  },
  quests: {
    key: "quests",
    label: "Квесты",
    basePath: "/admin/quests",
    columns: [
      { key: "name", label: "Название" },
      { key: "condition_type", label: "Условие" },
      { key: "target_value", label: "Цель" },
    ],
    fields: [
      { key: "code", label: "Код", type: "text", createOnly: true },
      { key: "name", label: "Название", type: "text" },
      { key: "description", label: "Описание", type: "textarea" },
      { key: "condition_type", label: "Тип условия", type: "select", options: CONDITION_TYPE_OPTIONS },
      { key: "target_value", label: "Целевое значение", type: "number" },
      { key: "reward_xp", label: "Награда XP", type: "number" },
      { key: "reward_coins", label: "Награда монет", type: "number" },
      { key: "sort_order", label: "Порядок сортировки", type: "number", defaultValue: 0 },
    ],
    hooks: makeAdminResourceHooks<QuestDefinitionAdminOut, unknown, unknown>("quests", "/admin/quests"),
  },
};

export const RESOURCE_LIST = Object.values(RESOURCES);
