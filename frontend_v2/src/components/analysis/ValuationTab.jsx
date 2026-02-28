import DCFTable from '../DCFTable'
import CompTable from '../CompTable'
import SensitivityGrid from '../SensitivityGrid'
import FootballField from '../FootballField'
import ScenarioAnalysis from '../ScenarioAnalysis'
import EarningsModelTable from '../EarningsModelTable'
import PrecedentTransactionTable from '../PrecedentTransactionTable'
import MarkdownSection from './MarkdownSection'
import FinancialsTab from './FinancialsTab'

/**
 * Unified Financials & Valuation tab. Combines valuation methods (football field,
 * DCF, scenarios, comps, precedent M&A, earnings model, sensitivity) with
 * financial statements. Empty subsections are hidden rather than showing placeholders.
 */

function ValuationSubsection({ title, subtitle, children }) {
  return (
    <div className="pb-8">
      <h3 className="text-xl font-bold text-primary">{title}</h3>
      <p className="text-sm text-tertiary mt-1 mb-4">{subtitle}</p>
      {children}
    </div>
  )
}

function ValuationTab({
  sections, dcf, sensitivity, conviction,
  scenarios, footballField, earningsModel,
  precedents, sensitivityOperating,
  financialStatements, financialsLoading, companyInfo,
}) {
  const hasFootballField = (footballField?.ranges?.length > 0) || sections.football_field
  const hasDCF = dcf || sections.dcf
  const hasScenario = scenarios || sections.scenarios
  const hasComps = !!sections.comps?.content && !sections.comps.content.includes('could not be performed')
  const hasPrecedent = precedents?.deals?.length > 0 ||
    (sections.precedents?.content && !sections.precedents.content.match(/could not be performed|no comparable|no relevant|no transactions/i))
  const hasEarnings = (earningsModel?.rows?.length > 0) || sections.earnings_model
  const hasSensitivity = (sensitivity?.fair_value_grid && (sensitivity?.wacc_values || sensitivity?.growth_values) && (sensitivity?.terminal_growth_values || sensitivity?.margin_values)) || sections.sensitivity
  const hasFinancials = financialsLoading || financialStatements?.is_available

  return (
    <div className="space-y-10">
      {hasFootballField && (
        <ValuationSubsection title="Valuation Football Field" subtitle="Cross-method valuation range comparison">
          {footballField ? (
            <FootballField data={footballField} />
          ) : (
            <MarkdownSection content={sections.football_field.content} />
          )}
        </ValuationSubsection>
      )}

      {hasDCF && (
        <ValuationSubsection title="DCF Valuation" subtitle="Discounted cash flow model with LLM-reasoned assumptions">
          {dcf ? (
            <DCFTable dcf={dcf} />
          ) : (
            <MarkdownSection content={sections.dcf.content} />
          )}
        </ValuationSubsection>
      )}

      {hasScenario && (
        <ValuationSubsection title="Scenario Analysis" subtitle="Bull / Base / Bear probability-weighted fair value">
          {scenarios ? (
            <ScenarioAnalysis scenarios={scenarios} />
          ) : (
            <MarkdownSection content={sections.scenarios.content} />
          )}
        </ValuationSubsection>
      )}

      {hasComps && (
        <ValuationSubsection title="Comparable Companies" subtitle="Peer valuation comparison">
          <CompTable content={sections.comps.content} />
        </ValuationSubsection>
      )}

      {hasPrecedent && (
        <ValuationSubsection title="Precedent M&A Transactions" subtitle="Recent comparable M&A deal multiples">
          {precedents?.deals?.length ? (
            <PrecedentTransactionTable data={precedents} />
          ) : (
            <MarkdownSection content={sections.precedents.content} />
          )}
        </ValuationSubsection>
      )}

      {hasEarnings && (
        <ValuationSubsection title="Earnings Model" subtitle="Historical actuals and analyst forecasts">
          {earningsModel ? (
            <EarningsModelTable data={earningsModel} />
          ) : (
            <MarkdownSection content={sections.earnings_model.content} />
          )}
        </ValuationSubsection>
      )}

      {hasSensitivity && (
        <ValuationSubsection title="Sensitivity Analysis" subtitle="Fair value across different WACC and terminal growth assumptions">
          {sensitivity ? (
            <SensitivityGrid data={sensitivity} />
          ) : (
            <MarkdownSection content={sections.sensitivity.content} />
          )}
        </ValuationSubsection>
      )}

      {sensitivityOperating?.fair_value_grid && (sensitivityOperating?.wacc_values || sensitivityOperating?.growth_values) && (sensitivityOperating?.terminal_growth_values || sensitivityOperating?.margin_values) && (
        <ValuationSubsection title="Operating Leverage Sensitivity" subtitle="Fair value across different revenue growth and margin assumptions">
          <SensitivityGrid
            data={sensitivityOperating}
            title="Revenue Growth vs Operating Margin"
            subtitle="Fair value per share across different operating assumptions"
            rowLabel="Growth"
            colLabel="Margin"
          />
        </ValuationSubsection>
      )}

      {hasFinancials && (
        <>
          <hr className="border-border-light" />
          <FinancialsTab
            financialStatements={financialStatements}
            financialsLoading={financialsLoading}
            companyInfo={companyInfo}
          />
        </>
      )}
    </div>
  )
}

export default ValuationTab
