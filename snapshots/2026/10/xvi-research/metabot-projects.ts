import type { ProjectSummary } from '../../lib/api';

/**
 * Stable, read-only projection of the Personal Edition's company core.
 * These anchors intentionally live in presentation code: they do not create
 * a second persisted hierarchy or alter T5T ownership semantics.
 */
export const CORE_PORTFOLIO_SLUGS = [
  'wbc',
  'vlm-brain',
  'g1-wuji-teleoperation',
  'humanoid-foundation',
  'matrix-agentvla',
  'xviinfra',
  'metabot',
] as const;

const CORE_PORTFOLIO_SET = new Set<string>(CORE_PORTFOLIO_SLUGS);

export function corePortfolioProjects(projects: ProjectSummary[]): ProjectSummary[] {
  const bySlug = new Map(projects.map((project) => [project.slug, project]));
  return CORE_PORTFOLIO_SLUGS.flatMap((slug) => {
    const project = bySlug.get(slug);
    return project ? [project] : [];
  });
}

export function isCorePortfolioProject(project: ProjectSummary): boolean {
  return CORE_PORTFOLIO_SET.has(project.slug);
}
