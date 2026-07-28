using System;
using System.Collections.Generic;
using SabberStoneCoreAi.MCGS.Abstraction;
using SabberStoneCoreAi.MCGS.Heuristics;
using SabberStoneCoreAi.MCGS.SabberHelper.Option;
using SabberStoneCoreAi.MCGS.Utils;
using SabberStoneCore.Enums;
using SabberStoneCore.Model;
using SabberStoneCore.Model.Entities;
using SabberStoneCore.Tasks.PlayerTasks;
using static SabberStoneCoreAi.MCGS.Utils.CommonUtils;

namespace SabberStoneCoreAi.MCGS
{
	partial class Node
    {
        // TODO: Don't need to calculate abstractions here; we just can get them from Abstraction
        public static PlayerTask[] GetPrunedAction_modified(Game g, Options options, bool simpleAbstraction, Dictionary<int, int[]> hashDic)
        {
            //Controller c = options.Controller;
            Controller c = g.CurrentPlayer;
            //Game g = c.Game;
            ReadOnlySpan<Minion> board;

            // No available actions when the game is in terminal state.
            if (g.State == State.COMPLETE)
                return new PlayerTask[0];

            // Nothing to prune for choices
            if (c.Choice != null)
            {
				int count = c.Choice.Choices.Count;
                var chooseTasks = new PlayerTask[count];
                //return options.Translate();
                for (int i = 0; i < count; i++)
                    chooseTasks[i] = ChooseTask.Pick(c, c.Choice.Choices[i]);

                return chooseTasks;
            }



            // TODO: Check lethal

            // TODO: Restore-effect cards

            Filters.CompulsiveAttackWhenAvailable(g, options);

            if (options.PlayableCount > 0)
            {
                var playOptions = options.PlayCardOptions;

                //bool pass = false;
                //bool modularChecked = false;

                board = c.BoardZone.GetSpan();

                // Prune actions of duplicate sources
                List<int[]> sourceHashes = new List<int[]>(options.PlayableCount);
                List<int[]> targetHashes = new List<int[]>();
                List<int> distinctTargetIds = new List<int>();
                IntSet consideredTargetIds = new IntSet();
                for (int i = playOptions.Count - 1; i >= 0; i--)
                {
                    IPlayable source = playOptions[i].Source;

                    // Extract distinct sources
                    if (!sourceHashes.TryAdd(
                        //StateAbstraction.PlayableHash(source), 
                        hashDic[source.Id],
                        IntArrComparer))
                    {
                        playOptions.RemoveAt(i);
                        options.PlayableCount--;
                        continue;
                    }

                    // Extract distinct targets here.
                    if (playOptions[i].HasTargets)
                    {
                        for (int j = 0; j < playOptions[i].Targets.Length; j++)
                        {
                            // Check the target's hash is already calculated.
                            // Calculate the hash of the target and check it is distinct.
                            int id = playOptions[i].Targets[j].Id;
                            if (consideredTargetIds.TryAdd(id) && 
                                targetHashes.TryAdd(
                                    //StateAbstraction.PlayableHash(playOptions[i].Targets[j]),
                                    hashDic[id],                                    
                                    IntArrComparer))
                                distinctTargetIds.Add(id);
                        }
                    }

                    //if (!pass && CardCategory.AdjacentEffectMinions.Contains(source.Card.AssetId))
                    //    pass = true;

                    //// Search for Mech minion when modular 
                    //if (!modularChecked && source.Card.Modular)
                    //{
                    //    for (int j = 0; j < board.Length; j++)
                    //    {
                    //        if (board[j].Card.Race == Race.MECHANICAL)
                    //        {
                    //            pass = true;
                    //            break;
                    //        }
                    //    }

                    //    modularChecked = true;
                    //}
                }

                // Remove actions with duplicate targets
                for (int i = playOptions.Count - 1; i >= 0; i--)
                {
                    if (!playOptions[i].HasTargets) continue;

                    var filtered = playOptions[i].Targets.FilterSmallArray(p => distinctTargetIds.Contains(p.Id));
                    if (filtered.Length == 0)
                        playOptions.RemoveAt(i);
                    else
                        playOptions[i] = playOptions[i].ChangeTargets(filtered);
                        //playOptions.SetValue(i, playOptions[i].ChangeTargets(filtered));
                }


                // For SimpleAbstraction
                // Stop considering positions unless the source has adjacent effect (e.g. Fungalmancer)
                // or modular minions are on the board.
                // TODO: consider Supercollider or Scourgelord Garrosh

                if (simpleAbstraction)
                {
                    bool adjExists = false; 

                    // Check adjacent minions on board.
                    // Should not remove considering position when adjacent auras exist.
                    for (int i = 0; i < board.Length; i++)
                        if ((board[i].Card.AssetId == 985 || board[i].Card.AssetId == 1008) && board[i].IsSilenced)
                        {
                            adjExists = true;
                            break;
                        }

                    if (!adjExists)
                    {
                        // Remove positions unless the source is adjacent card or modular.
                        bool modularChecked = false;
                        bool mechExists = false;
                        for (int i = 0; i < playOptions.Count; i++)
                        {
                            if (!(playOptions[i].Source is Minion m)) continue;

                            if (CardCategory.AdjacentEffectMinions.Contains(m.Card.AssetId))
                                continue;

                            if (m.Card.Modular)
                            {
                                if (!modularChecked)
                                {
                                    for (int j = 0; j < board.Length; j++)
                                    {
                                        if (board[j].Card.Race == Race.MECHANICAL)
                                        {
                                            mechExists = true;
                                            break;
                                        }
                                    }

                                    modularChecked = true;

                                    if (mechExists)
                                        continue;
                                }
                                else if (mechExists)
                                    continue;
                            }

                            playOptions[i] = playOptions[i].RemoveZonePosRange();
                            //playOptions.SetValue(i, playOptions[i].RemoveZonePosRange());
                        }
                    }
                }


                //if (!pass && simpleAbstraction)
                //{
                //    // Check adjacent minions on board
                //    for (int i = 0; i < board.Length; i++)
                //        if ((board[i].Card.AssetId == 985 || board[i].Card.AssetId == 1008) && board[i].IsSilenced)
                //        {
                //            pass = true;
                //            break;
                //        }

                //    if (!pass)
                //        for (var i = 0; i < playOptions.Count; i++)
                //            if (playOptions[i].Source is Minion)
                //                playOptions[i] = playOptions[i].RemoveZonePosRange();
                //}
                
            }

            if (options.AttackerCount > 0)
            {
                List<AttackOption> attackOptions = options.AttackOptions;
                Minion[] minionTargets = attackOptions[0].Targets;
                
                // Remove attacks to duplicate defenders
                if (minionTargets.Length > 0)
                {
                    List<int[]> hashes = new List<int[]>(minionTargets.Length);
                    Minion[] distinctTargets = minionTargets.FilterSmallArray(p =>
                        hashes.TryAdd(
                            //StateAbstraction.PlayableHash(p),
                            hashDic[p.Id],
                            IntArrComparer));

                    if (distinctTargets.Length != minionTargets.Length)
                        for (int i = 0; i < attackOptions.Count; i++)
                            attackOptions[i] = attackOptions[i].ChangeTargets(distinctTargets);
                }


                // Remove duplicate attackers
                for (int i = 0; i < attackOptions.Count; i++)
                {
                    List<int[]> hashes = new List<int[]>(options.AttackerCount);

                    for (int j = attackOptions.Count - 1; j >= 0; j--)
                    {
                        var hash = attackOptions[j].Source == null ? 
                            StateAbstraction.PlayableHash(c.Hero) : 
                            hashDic[attackOptions[j].Source.Id];

                        if (!hashes.TryAdd(
                            //StateAbstraction.PlayableHash(attackOptions[j].Source ?? c.Hero), 
                            hash,
                            IntArrComparer))
                        {
                            attackOptions.RemoveAt(j);
                            options.AttackerCount--;
                        }
                    }
                }
            }

            Filters.RemoveVoidAction(g, options);
            Filters.CompulsiveHeroPowerWhenAvailable(g, options);


            return options.Translate(c);
        }
    }
}
