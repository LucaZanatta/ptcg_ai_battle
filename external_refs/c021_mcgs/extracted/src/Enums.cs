namespace SabberStoneCoreAi.MCGS
{
	public enum RandomActionType
	{
		FALSE, RANDOMEFFECT, CHOICES, ENDTURN, ENDTURN_OPPONENT, DRAW, SECRET, TRACKING
	}
	public enum InspectType
	{
		ATTACK, ATTACKWITHAMINION, ATTACKMINION, ATTACKHERO, PLAYMINION, PLAYSPELL, PLAYSPELLTOTARGET, KILLMINION, DAMAGEHERO, KILLHERO
	}

	public enum EndNodeOption
	{
		DEFAULT, SEPARATED_SAMPLE_WIDTH, SEPARATED_AND_REDUCED, ROOTPARALLEL
	}

	public enum SearchDurationControlOption
	{
		DURATION_ARITHMETIC, /*DURATION_PROPORTIONTOBREADTH*/ DURATION_EXPONENTIAL, DURATION_STATIONARY, FIRSTONLY, SEARCHCOUNT, DEBUG, COMPENSATE
	}

	public enum ImperfectInformationAlgorithm
	{
		DEFAULT, PIMC, SO_ISMCTS
	}

	public enum SelectionStrategy
	{
		UCT, D_UCT, UCD
	}

	public enum FinalMoveSelection
	{
		MaxChild, RobustChild, RobustMaxChild, SecureChild
	}
}
