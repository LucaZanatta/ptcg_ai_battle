using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using SabberStoneCoreAi.MCGS.Abstraction;
using SabberStoneCoreAi.MCGS.Utils;
using SabberStoneCore.Model;
using SabberStoneCore.Model.Entities;
using SabberStoneCore.Model.Zones;
using SabberStoneCore.Enums;

namespace SabberStoneCoreAi.MCGS
{
    partial class Node
    {
        private HashSet<Information> _informationSet;
        private List<Game> _games;

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public void AddGame(Game game)
        {
            if (_games == null)
                _games = new List<Game> {Game, game};
            else
                _games.Add(game);
        }

        public bool HasMultipleGame => _games?.Count > 0;

        public bool IsInformationSet => _informationSet != null;

        private Information ExtractPrivateInformation()
        {
            TranspositionTable.Remove(StateAbstraction);

            Information info = StateAbstraction.ExtractPrivateInformation(
                Game.CurrentOpponent.HandZone.GetSpan());

            return info;
        }

        private static bool GetInformationSet(ref Node node)
        {
	        // 1. Extract private information of the root player.
            Information info = node.ExtractPrivateInformation();

            Node matching = node;
            // 2. Look up transposition table
            if (MonteCarloGraphSearch.TranspositionCheck(ref matching))
            {   // Matching information set is found.
                if (!matching.IsInformationSet) throw new Exception();

                // Check if there is duplicated information.
                //if (!matching._informationSet.Add(info))
                //    throw new Exception();
                matching._informationSet.Add(info);

                node = matching;
                return true;
            }
            // 3. Creates a new information set
            else
            {
                node._informationSet = new HashSet<Information> {info};
                return false;
            }
        }

        private bool RestoreNodes(out Node newNode)
        {
	        var original = Game;
            var aa = new ActionAbstraction(ChanceAction, MCGS.NodeConfig.SimpleAbstraction);

            Information currentInfo = StateAbstraction.ExtractPrivateInformation(
                Game.CurrentOpponent.HandZone.GetSpan());

			foreach (Information info in _informationSet)
            {
                if (info == currentInfo)
	                Game.CurrentOpponent.DeckZone.Shuffle();
                else
                {
	                try
	                {
		                // Prepare private information
		                var g = original.Clone();
		                {
			                Controller c = g.CurrentOpponent;
			                HandZone handZone = c.HandZone;
			                EntityList dict = g.IdEntityDic;
			                ReadOnlySpan<IPlayable> hand = info.HandMemory.Span;

			                IPlayable[] buffer = new IPlayable[hand.Length];
			                int k = 0;
			                for (int i = 0; i < hand.Length; i++)
			                {
				                if (dict.TryGetValue(hand[i].Id, out IPlayable toBeReplaced))
				                {
					                IZone zone = toBeReplaced.Zone;
					                if (zone.Type != Zone.HAND && zone.Type != Zone.DECK)
						                continue;
					                zone.Remove(toBeReplaced);
				                }
				                buffer[k++] = hand[i].Clone(in c);
			                }

			                g.AuraUpdate();

							// How should we handle the changes?
							// The private information must be restored before
							// the endturn - starturn session is processed
							if (handZone.Count > 0 && hand.Length > 0)
							{
								var deckZone = c.DeckZone;
								//var dictMemory = hand[0].Game.IdEntityDic;
								var deckMemory = hand[0].Controller.DeckZone.GetSpan();
								for (int i = handZone.Count - 1; i >= 0; --i)
								{
									int id = handZone[i].Id;
									bool flag = false;
									for (int j = 0; j < deckMemory.Length; j++)
									{
										if (deckMemory[j].Id == id)
										{
											deckZone.Add(handZone.Remove(handZone[i]));
											flag = true;
											break;
										}
									}

									if (!flag)
									{	// This entity is not in hand or deck
										// when the information is extracted
										// but currently in the current hand.
										// if it was removed at that time,
										// it should not exist at this time too.
										if (!hand[0].Game.IdEntityDic.TryGetValue(id, out IPlayable entity))
											continue; // This entity is created during the opponent's turn.
										Zone memoryZone = entity.Zone.Type;
										if (memoryZone == Zone.GRAVEYARD ||
										    memoryZone == Zone.SETASIDE)
											handZone.Remove(handZone[i]);
										// This entity is returned to hand.
									}
										
								}
								g.AuraUpdate();
							}

							for (int i = 0; i < k; i++)
							{
								buffer[i].ActivatedTrigger?.Remove();
								handZone.Add(buffer[i]);
							}

							g.AuraUpdate();
		                }

		                Game = g;
	                }
	                catch 
	                {
		                continue;
	                }
                }

                // Expand new sample node for each private information
                Node sample = new Node(this, ChanceAction, 0, aa);
					
                sample._informationSet = null;

                // Check transposition
                if (MCGS.NodeConfig.Transposition)
	                MonteCarloGraphSearch.TranspositionCheck(ref sample);
            }
			
            // Take one of the samples;
            newNode = OutgoingEdges[_rnd.Next(OutgoingEdges.Count)].Successor;
            return newNode.IsTransposition;
        }
    }

    public readonly struct Information : IEquatable<Information>
    {
	    //public readonly int[] HandIds;
        private readonly int _hashCode;

        public readonly ReadOnlyMemory<IPlayable> HandMemory;

        public Information(in int[][] handHashes, in ReadOnlySpan<IPlayable> handSpan)
        {
	        HandMemory = new ReadOnlyMemory<IPlayable>(handSpan.ToArray());
	        //HandIds = handIds;

            _hashCode = IntArrayComparer.ArrayHashCode(handHashes);


			//_handHashes = handHashes;
        }

        public override string ToString()
        {
            return HandMemory.Span[HandMemory.Length - 1].Card.Name;
        }

        #region Equality members
        public bool Equals(Information other) => _hashCode == other._hashCode;
        public override bool Equals(object obj) => obj is Information info && Equals(info);
        public override int GetHashCode() => _hashCode;
        public static bool operator ==(Information left, Information right) => Equals(left, right);
        public static bool operator !=(Information left, Information right) => !Equals(left, right);
        #endregion
    }
}
