import DCFTable from '../DCFTable'
import CompTable from '../CompTable'
import SensitivityGrid from '../SensitivityGrid'
import FootballField from '../FootballField'
import ScenarioAnalysis from '../ScenarioAnalysis'
import EarningsModelTable from '../EarningsModelTable'
import PrecedentTransactionTable from '../PrecedentTransactionTable'
import MarkdownSection from './MarkdownSection'

/**
 * Valuation tab composing all valuation methods:
 * football field, DCF, scenario analysis, comps, precedent M&A, earnings model, sensitivity.
 */

function ValuationSubsection({ title, subtitle, children, showBorder = true }) {
  return (
    <div className={showBorder ? 'border-b border-slate-200 pb-8' : ''}>
      <h3 className="text-xl font-bold text-slate-800">{title}</h3>
      <p className="text-sm text-slate-500 mt-1 mb-4">{subtitle}</p>
      {children}
    </div>
  )
}

function ValuationTab({
  sections, dcfModel, sensitivityData, convictionData,
  scenarioData, footballFieldData, earningsModelData,
  precedentData, growthMarginSensitivityData,
}) {
  return (
    <div className="space-y-10">
      <ValuationSubsection title="Valuation Football Field" subtitle="Cross-method valuation range comparison">
        {footballFieldData ? (
          <FootballField footballFieldData={footballFieldData} />
        ) : sections.football_field ? (
          <MarkdownSection content={sections.football_field.content} />
        ) : <p className="text-sm text-slate-400 italic">Football field not yet available</p>}
      </ValuationSubsection>

      <ValuationSubsection title="DCF Valuation" subtitle="Discounted cash flow model with LLM-reasoned assumptions">
        {dcfModel ? (
          <DCFTable dcfModel={dcfModel} />
        ) : sections.dcf_valuation ? (
          <MarkdownSection content={sections.dcf_valuation.content} />
        ) : <p className="text-sm text-slate-400 italic">DCF model not yet available</p>}
      </ValuationSubsection>

      <ValuationSubsection title="Scenario Analysis" subtitle="Bull / Base / Bear probability-weighted fair value">
        {scenarioData ? (
          <ScenarioAnalysis scenarioData={scenarioData} />
        ) : sections.scenario_analysis ? (
          <MarkdownSection content={sections.scenario_analysis.content} />
        ) : <p className="text-sm text-slate-400 italic">Scenario analysis not yet available</p>}
      </ValuationSubsection>

      <ValuationSubsection title="Comparable Companies" subtitle="Peer valuation comparison">
        {sections.comp_table ? (
          <CompTable content={sections.comp_table.content} />
        ) : <p className="text-sm text-slate-400 italic">Comparable analysis not yet available</p>}
      </ValuationSubsection>

      <ValuationSubsection title="Precedent M&A Transactions" subtitle="Recent comparable M&A deal multiples">
        {precedentData ? (
          <PrecedentTransactionTable precedentData={precedentData} />
        ) : sections.precedent_transactions ? (
          <MarkdownSection content={sections.precedent_transactions.content} />
        ) : <p className="text-sm text-slate-400 italic">Precedent transactions not yet available</p>}
      </ValuationSubsection>

      <ValuationSubsection title="Earnings Model" subtitle="Historical actuals and analyst forecasts">
        {earningsModelData ? (
          <EarningsModelTable earningsModelData={earningsModelData} />
        ) : sections.earnings_model ? (
          <MarkdownSection content={sections.earnings_model.content} />
        ) : <p className="text-sm text-slate-400 italic">Earnings model not yet available</p>}
      </ValuationSubsection>

      <ValuationSubsection title="Sensitivity Analysis" subtitle="Fair value across different WACC and terminal growth assumptions" showBorder={!!growthMarginSensitivityData}>
        {sensitivityData ? (
          <SensitivityGrid sensitivityData={sensitivityData} />
        ) : sections.sensitivity ? (
          <MarkdownSection content={sections.sensitivity.content} />
        ) : <p className="text-sm text-slate-400 italic">Sensitivity analysis not yet available</p>}
      </ValuationSubsection>

      {growthMarginSensitivityData && (
        <ValuationSubsection title="Operating Leverage Sensitivity" subtitle="Fair value across different revenue growth and margin assumptions" showBorder={false}>
          <SensitivityGrid
            sensitivityData={growthMarginSensitivityData}
            title="Revenue Growth vs Operating Margin"
            subtitle="Fair value per share across different operating assumptions"
            rowLabel="Growth"
            colLabel="Margin"
          />
        </ValuationSubsection>
      )}
    </div>
  )
}

export default ValuationTab
