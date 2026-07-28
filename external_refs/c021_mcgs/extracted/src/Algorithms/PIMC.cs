using System;
using System.Collections.Generic;
using SabberStoneCoreAi.MCGS.Abstraction;
using SabberStoneCoreAi.MCGS.SabberHelper;
using SabberStoneCore.Model;
using SabberStoneCore.Model.Entities;

namespace SabberStoneCoreAi.MCGS.Algorithms
{
    static class PerfectInformationMonteCarlo
    {
        public static Node[] GenerateDeterminizationsAtOnce(Game game, int num, NodeConfig nodeConfig, NodeConfig opConfig)
        {
            var rnd = new Random();

            var set = new HashSet<int>();

            var nodes = new List<Node>();

            for (int i = 0; i < num; i++)
            {
                var clone = game.Clone();
                SabberUtils.Determinize(clone, rnd, true);

                int hash = clone.DeterminizationHash();

                if (!set.Add(hash)) continue;

                nodes.Add(new Node(clone, nodeConfig, opConfig));
            }

            return nodes.ToArray();
        }

        private static int DeterminizationHash(this Game game)
        {
            // 1. The order of cards in the current player's deck
            // 2. The order of cards in the current opponent's deck
            // 3. The cards in the current opponent's hand

            var deck = game.CurrentPlayer.DeckZone.GetSpan();
            
            int hc = deck.Length;
            for (int i = 0; i < deck.Length; i++)
                hc = unchecked(hc * 17 + deck[i].Card.AssetId);

            deck = game.CurrentOpponent.DeckZone.GetSpan();
            for (int i = 0; i < deck.Length; i++)
                hc = unchecked(hc * 17 + deck[i].Card.AssetId);

            ReadOnlySpan<IPlayable> hand = game.CurrentOpponent.HandZone.GetSpan();

            var buffer = new int[hand.Length][];

            for (int i = 0; i < buffer.Length; i++)
                buffer[i] = StateAbstraction.PlayableHash(hand[i]);

            Array.Sort(buffer, new Utils.IntArrayComparer());

            hc = unchecked(hc * 17 + Utils.IntArrayComparer.ArrayHashCode(buffer));

            return hc;
        }
    }
}
