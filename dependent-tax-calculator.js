#!/usr/bin/env node

/**
 * Dependent Tax Calculator
 *
 * Calculates how much more you'd take home weekly by claiming
 * dependents on your W-4 vs. claiming none.
 *
 * Based on 2025 US federal tax brackets and W-4 rules.
 */

// 2025 Federal Tax Brackets (Single filer)
const SINGLE_BRACKETS = [
  { min: 0,       max: 11925,   rate: 0.10 },
  { min: 11925,   max: 48475,   rate: 0.12 },
  { min: 48475,   max: 103350,  rate: 0.22 },
  { min: 103350,  max: 197300,  rate: 0.24 },
  { min: 197300,  max: 250525,  rate: 0.32 },
  { min: 250525,  max: 626350,  rate: 0.35 },
  { min: 626350,  max: Infinity, rate: 0.37 },
];

// 2025 Federal Tax Brackets (Married Filing Jointly)
const MFJ_BRACKETS = [
  { min: 0,       max: 23850,   rate: 0.10 },
  { min: 23850,   max: 96950,   rate: 0.12 },
  { min: 96950,   max: 206700,  rate: 0.22 },
  { min: 206700,  max: 394600,  rate: 0.24 },
  { min: 394600,  max: 501050,  rate: 0.32 },
  { min: 501050,  max: 751600,  rate: 0.35 },
  { min: 751600,  max: Infinity, rate: 0.37 },
];

// 2025 Federal Tax Brackets (Head of Household)
const HOH_BRACKETS = [
  { min: 0,       max: 17000,   rate: 0.10 },
  { min: 17000,   max: 64850,   rate: 0.12 },
  { min: 64850,   max: 103350,  rate: 0.22 },
  { min: 103350,  max: 197300,  rate: 0.24 },
  { min: 197300,  max: 250500,  rate: 0.32 },
  { min: 250500,  max: 626350,  rate: 0.35 },
  { min: 626350,  max: Infinity, rate: 0.37 },
];

// Standard deductions for 2025
const STANDARD_DEDUCTIONS = {
  single: 15000,
  married: 30000,
  head_of_household: 22500,
};

// W-4 dependent credits (annual amounts from Step 3)
const CHILD_DEPENDENT_CREDIT = 2000;  // per qualifying child under 17
const OTHER_DEPENDENT_CREDIT = 500;   // per other dependent

function getBrackets(filingStatus) {
  switch (filingStatus) {
    case 'married': return MFJ_BRACKETS;
    case 'head_of_household': return HOH_BRACKETS;
    default: return SINGLE_BRACKETS;
  }
}

function calculateFederalTax(taxableIncome, filingStatus) {
  const brackets = getBrackets(filingStatus);
  let tax = 0;
  for (const bracket of brackets) {
    if (taxableIncome <= bracket.min) break;
    const taxableInBracket = Math.min(taxableIncome, bracket.max) - bracket.min;
    tax += taxableInBracket * bracket.rate;
  }
  return tax;
}

function calculateWithholding(annualGross, filingStatus, childDependents, otherDependents) {
  const standardDeduction = STANDARD_DEDUCTIONS[filingStatus];
  const taxableIncome = Math.max(0, annualGross - standardDeduction);
  let tax = calculateFederalTax(taxableIncome, filingStatus);

  // Apply dependent credits (from W-4 Step 3)
  const totalCredits = (childDependents * CHILD_DEPENDENT_CREDIT)
                     + (otherDependents * OTHER_DEPENDENT_CREDIT);
  tax = Math.max(0, tax - totalCredits);

  return tax;
}

function formatCurrency(amount) {
  return '$' + amount.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function printReport(annualSalary, filingStatus) {
  console.log('='.repeat(60));
  console.log('  DEPENDENT TAX CALCULATOR — Weekly Take-Home Comparison');
  console.log('='.repeat(60));
  console.log();
  console.log(`  Annual Gross Salary:  ${formatCurrency(annualSalary)}`);
  console.log(`  Filing Status:        ${filingStatus.replace('_', ' ')}`);
  console.log(`  Tax Year:             2025`);
  console.log();
  console.log('-'.repeat(60));

  // Calculate with 0 dependents
  const tax0 = calculateWithholding(annualSalary, filingStatus, 0, 0);
  const weeklyTax0 = tax0 / 52;
  const weeklyNet0 = (annualSalary / 52) - weeklyTax0;

  // Calculate with 1 child dependent
  const tax1Child = calculateWithholding(annualSalary, filingStatus, 1, 0);
  const weeklyTax1Child = tax1Child / 52;
  const weeklyNet1Child = (annualSalary / 52) - weeklyTax1Child;

  // Calculate with 1 other dependent
  const tax1Other = calculateWithholding(annualSalary, filingStatus, 0, 1);
  const weeklyTax1Other = tax1Other / 52;
  const weeklyNet1Other = (annualSalary / 52) - weeklyTax1Other;

  const weeklyGross = annualSalary / 52;

  console.log();
  console.log('  Scenario                  Annual Tax   Weekly Tax   Weekly Net');
  console.log('  ' + '-'.repeat(56));
  console.log(`  0 dependents              ${formatCurrency(tax0).padStart(10)}   ${formatCurrency(weeklyTax0).padStart(10)}   ${formatCurrency(weeklyNet0).padStart(10)}`);
  console.log(`  1 child (under 17)        ${formatCurrency(tax1Child).padStart(10)}   ${formatCurrency(weeklyTax1Child).padStart(10)}   ${formatCurrency(weeklyNet1Child).padStart(10)}`);
  console.log(`  1 other dependent         ${formatCurrency(tax1Other).padStart(10)}   ${formatCurrency(weeklyTax1Other).padStart(10)}   ${formatCurrency(weeklyNet1Other).padStart(10)}`);
  console.log();
  console.log('-'.repeat(60));
  console.log();
  console.log('  EXTRA WEEKLY TAKE-HOME by claiming 1 dependent:');
  console.log();
  console.log(`    Child under 17:   +${formatCurrency(weeklyNet1Child - weeklyNet0)}/week  (+${formatCurrency(tax0 - tax1Child)}/year)`);
  console.log(`    Other dependent:  +${formatCurrency(weeklyNet1Other - weeklyNet0)}/week  (+${formatCurrency(tax0 - tax1Other)}/year)`);
  console.log();
  console.log('='.repeat(60));
  console.log();
  console.log('  NOTE: This is federal income tax only. It does not include');
  console.log('  Social Security (6.2%), Medicare (1.45%), or state taxes.');
  console.log('  Actual paycheck impact may vary based on your employer\'s');
  console.log('  withholding calculations and pay frequency.');
  console.log();
}

// --- Main ---
const args = process.argv.slice(2);

if (args.includes('--help') || args.includes('-h')) {
  console.log('Usage: node dependent-tax-calculator.js [annual_salary] [filing_status]');
  console.log();
  console.log('Arguments:');
  console.log('  annual_salary    Your annual gross salary (default: 50000)');
  console.log('  filing_status    single | married | head_of_household (default: single)');
  console.log();
  console.log('Examples:');
  console.log('  node dependent-tax-calculator.js 60000');
  console.log('  node dependent-tax-calculator.js 75000 married');
  console.log('  node dependent-tax-calculator.js 45000 head_of_household');
  process.exit(0);
}

const salary = parseFloat(args[0]) || 50000;
const status = (args[1] || 'single').toLowerCase();

if (!['single', 'married', 'head_of_household'].includes(status)) {
  console.error(`Invalid filing status: "${status}". Use: single, married, or head_of_household`);
  process.exit(1);
}

printReport(salary, status);
