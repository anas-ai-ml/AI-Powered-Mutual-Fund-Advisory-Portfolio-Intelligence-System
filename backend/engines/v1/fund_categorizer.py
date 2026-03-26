import pandas as pd
import logging

logger = logging.getLogger(__name__)


def categorize_funds(df: pd.DataFrame) -> pd.DataFrame:
    """
    Categorizes funds using keyword mapping on the Scheme Name.
    Large Cap, Mid Cap, Small Cap, Flexi Cap, Hybrid, Liquid -> Debt, Gold -> Gold
    Returns the dataframe with a new 'category' column.
    """
    if df is None or df.empty:
        return df

    logger.info("Categorizing funds into Asset Classes")

    # Create a copy to avoid SettingWithCopyWarning
    categorized_df = df.copy()

    # Initialize all with a default "Other" category
    categorized_df["category"] = "Other"

    # Keyword mappings (order matters for overlapping terms)
    # Using lowercase for case-insensitive matching
    categorized_df.loc[
        categorized_df["scheme_name"].str.lower().str.contains("large cap", na=False),
        "category",
    ] = "Large Cap"
    categorized_df.loc[
        categorized_df["scheme_name"].str.lower().str.contains("mid cap", na=False),
        "category",
    ] = "Mid Cap"
    categorized_df.loc[
        categorized_df["scheme_name"].str.lower().str.contains("small cap", na=False),
        "category",
    ] = "Small Cap"
    categorized_df.loc[
        categorized_df["scheme_name"].str.lower().str.contains("flexi cap", na=False),
        "category",
    ] = "Flexi"
    # Adding sectorals to aggressive mapping
    categorized_df.loc[
        categorized_df["scheme_name"].str.lower().str.contains("sector", na=False)
        | categorized_df["scheme_name"].str.lower().str.contains("thematic", na=False),
        "category",
    ] = "Sectoral"

    categorized_df.loc[
        categorized_df["scheme_name"].str.lower().str.contains("hybrid", na=False)
        | categorized_df["scheme_name"].str.lower().str.contains("balanced", na=False),
        "category",
    ] = "Hybrid"

    categorized_df.loc[
        categorized_df["scheme_name"].str.lower().str.contains("liquid", na=False)
        | categorized_df["scheme_name"].str.lower().str.contains("debt", na=False)
        | categorized_df["scheme_name"].str.lower().str.contains("bond", na=False),
        "category",
    ] = "Debt"

    categorized_df.loc[
        categorized_df["scheme_name"].str.lower().str.contains("gold", na=False),
        "category",
    ] = "Gold"

    # Filter out unclassified ones if we only want our core categories
    # categorized_df = categorized_df[categorized_df['category'] != 'Other']

    logger.info(
        f"Categorization complete. {len(categorized_df[categorized_df['category'] != 'Other'])} funds categorized out of {len(categorized_df)}."
    )
    return categorized_df
