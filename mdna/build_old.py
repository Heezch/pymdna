import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial.transform import Rotation as R
import mdtraj as md
from .spline import SplineFrames
from .generators import StructureGenerator
from .geometry import NucleicFrames
import pmcpy.run.equilibrate as em
from pmcpy.run.run import Run
import copy

class Build:

    def __init__(self, dna_a, dna_b=None, five_end='A', three_end='B', margin=1):
        self.dna_a = dna_a
        self.dna_b = dna_b
        self.frames_a = dna_a.frames if dna_a else None
        self.frames_b = dna_b.frames if dna_b else None
        self.five_end = five_end 
        self.three_end = three_end
        self.margin = margin
        self.bp_range = 100 # should double check what this does again
        self.tolerance = np.abs((360 / 10.4) - (360 / 10.6))

    def _initialize_pmcpy(self):

         # make a random seque`nce for the new spline
        if sequence is None:
            sequence = self.dna_a.sequence
        spline = self.dna_a.spline

        pos, triads = self.get_pos_and_triads(spline)
        mc = Run(triads=triads,positions=pos,sequence=sequence,closed=closed,endpoints_fixed=endpoints_fixed,fixed=fixed,temp=300,exvol_rad=exvol_rad)
        return  mc, spline


    def _get_positions_and_triads(self, out):
        positions =out['confs'][:,:,:3,3] # get the last positions
        triads = out['confs'][:,:,:3,:3]
        out['triads'] = triads[-1]
        out['positions'] = positions[-1]

        return positions, triads.transpose(0,1,3,2) # flip column vectors to row vectors

    def minimize(self, simple=True):

        minimizer = self._initialize_pmcpy()    
        if simple:
            out = minimizer.equilibrate_simple(equilibrate_writhe=False)
        else:
            out = minimizer.equilibrate()

        positions, triads = self._get_positions_and_triads(out)

        self.update_spline(spline, out)

    def run(self, cycles: int, dump_every: int = 0, start_id: int = 0) -> np.ndarray:
        """Run the Monte Carlo simulation."""

        mc = self._initialize_pmcpy()
        out = mc.run(cycles=cycles, dump_every=dump_every, start_id=start_id)

        positions, triads = self._get_positions_and_triads(out)





        #pmc = Run(triads=triads,positions=positions,sequence=None,closed=False,endpoints_fixed=False,fixed=[],temp=300,exvol_rad=1)
        
        # use .run(cycles: int, dump_every: int = 0, start_id: int = 0) 
        
        # only this one works to equilibrate writhe 
        # or .equilibrate_simple(self, 
                # equilibrate_writhe: bool = True, 
                # dump_every: int = 0,
                # cycles_per_eval: int = 3,
                # evals_per_average: int = 100,
                # init_cycle_multiplier: int = 4,
                # num_below_max: int = 3)

        # .equilibrate(dump_every: int = 0,
                    # cycles_per_eval: int = 5,
                    # min_evals: int = 100,
                    # plot_equi: bool = False,
                    # num_taus: int = 6)
        pass

    def equilibrate_writhe(self, sequence=None, closed=True, endpoints_fixed=False, fixed=[],exvol_rad=2):
        
        # make a random seque`nce for the new spline
        if sequence is None:
            sequence = self.dna_a.sequence
        spline = self.dna_a.spline
        pos, triads = self.get_pos_and_triads(spline)

        mc = Run(triads=triads,positions=pos,sequence=sequence,closed=closed,endpoints_fixed=endpoints_fixed,fixed=fixed,temp=300,exvol_rad=exvol_rad)
        out = mc.equilibrate_simple(equilibrate_writhe=True,
                                        dump_every= 1,
                                        cycles_per_eval = 3,
                                        evals_per_average= 100,
                                        init_cycle_multiplier = 4,
                                        num_below_max = 3)
        #self.update_spline(spline, out)

        positions =out['confs'][-1,:,:3,3] # get the last positions
        triads = out['confs'][-1,:,:3,:3] # get the last triads 
        traids = triads.transpose((0, 2, 1)) # transpose the triad to flip the rows and columns vectors
        out['triads'] = triads
        out['positions'] = positions
        self.out = out
        self.update_spline(spline, out)
        dna = StructureGenerator(self.dna_a.spline,sequence=sequence)
        return dna



    def equilibrate(self, sequence=None, closed=False, endpoints_fixed=False, fixed=[],exvol_rad=0):

        # make a random seque`nce for the new spline
        if sequence is None:
            sequence = self.dna_a.sequence

        # minimize the new spline with the fixed frames of A and B
        self.out = self.minimize_spline(self.dna_a.spline, 
                                        sequence=sequence, 
                                        closed=closed, 
                                        endpoints_fixed=False, 
                                        fixed=fixed, 
                                        exvol_rad=exvol_rad
                                        )

        dna = StructureGenerator(self.dna_a.spline,sequence=sequence)
        return dna 
    
    def get_pos_and_triads(self, spline):
        # get origins of the base pair frames and the triads of the base pair frames (as column vectors for each frame)
        return spline.frames[:,0,:], spline.frames[:,1:,:].transpose((0, 2, 1))

    def update_spline(self, spline, out):
        # update the spline with new positions and triads
        spline.frames[:,0,:] = out['positions'] # set the origins of the frames
        spline.frames[:,1:,:] = out['triads'].transpose((0, 2, 1))# set the triads of the frames as row vectors
        
    def minimize_spline(self,spline, fixed=[], closed=False, sequence=None, endpoints_fixed=False, exvol_rad=0):

        """ Minimize the spline using the fixed frames of A and B.
        Note does not work with excluded volumes yet"""

        # get the positions and triads of the base pair frames
        pos, triads = self.get_pos_and_triads(spline)

        # # start with temperature annealing at 100000K
        # pmc = Run(triads,pos,sequence=sequence,closed=closed,endpoints_fixed=endpoints_fixed,fixed=fixed,temp=300,exvol_rad=exvol_rad)
        # out = pmc.equilibrate_simple()#cycles_per_eval=100)


        # start with temperature annealing at 100000K
        out  = em.equilibrate(triads,pos,sequence=sequence,closed=closed,endpoints_fixed=endpoints_fixed,fixed=fixed,temp=100000,num_cycles=100,exvol_rad=0)
        positions =out['confs'][-1,:,:3,3] # get the last positions
        triads = out['confs'][-1,:,:3,:3] # get the last triads 
        traids = triads.transpose((0, 2, 1)) # transpose the triad to flip the rows and columns vectors
        out['triads'] = triads
        out['positions'] = positions

        out = em.equilibrate(out['triads'],out['positions'],sequence=sequence,closed=closed,endpoints_fixed=endpoints_fixed,fixed=fixed,temp=300,exvol_rad=exvol_rad)
        positions =out['confs'][-1,:,:3,3] # get the last positions
        triads = out['confs'][-1,:,:3,:3] # get the last triads 
        traids = triads.transpose((0, 2, 1)) # transpose the triad to flip the rows and columns vectors
        out['triads'] = triads
        out['positions'] = positions
        #pmc = Run(out_hot['triads'],out_hot['positions'],sequence=sequence,closed=closed,endpoints_fixed=endpoints_fixed,fixed=fixed,temp=300,exvol_rad=exvol_rad)
        #out = pmc.equilibrate()
        # update the spline with the new positions and triads
        self.update_spline(spline, out)
        return out

    def connect(self,nbp=None, control_points=None,index=0):

        if not self.dna_b:
            raise ValueError("No second DNA sequence provided for connection.")
        
        # get the start and end of the connection
        self.get_start_and_end()

        # compute the rotation difference between the two frames (aka difference in twist per base pair)
        rotation_difference = self.get_twist_difference(self.start, self.end)

        if nbp is None:
            # find optimal number of base pairs for the given range
            optimal_bps = self.find_optimal_bps(np.array([self.start[0], self.end[0]]), 
                                                bp_per_turn=10.5, 
                                                rise=0.34, 
                                                bp_range=self.bp_range, 
                                                rotation_difference=rotation_difference, 
                                                tolerance=self.tolerance, 
                                                plot=False
                                                )
            
            # get the optimal number of base pairs (smallest amount of base pairs that satisfies the tolerance)
            number_of_bp = optimal_bps[index]['optimal_bp']
        else:
            number_of_bp = nbp
        
        # interpolate control points for spline C
        if control_points is None:
            control_points_C = self.interplotate_points(self.start[0], self.end[0], number_of_bp)
            distance = np.linalg.norm(self.start-self.end)
            self.control_points_C = control_points_C    
            spline_C = SplineFrames(control_points_C,frame_spacing=distance/len(control_points_C))
        else:
            control_points_C = control_points
            self.control_points_C = control_points_C   
            spline_C = SplineFrames(control_points_C,frame_spacing=0.34, initial_frame=self.start)

    
        # combine splines A B and C and remember the fixed nodes/frames of A and B
        # exclude first and last frame of A and B
        spline_C.frames = np.concatenate([self.frames_a[:-1],spline_C.frames,self.frames_b[1:]])
        self.spline_C_raw = copy.deepcopy(spline_C)
        # fix first and last 45 indices of total length of 257 frames
        fixed = list(range(self.frames_a.shape[0]-self.margin))+list(range(spline_C.frames.shape[0]-self.frames_b.shape[0]+self.margin,spline_C.frames.shape[0]))
        print('f',fixed)
        print('c',spline_C.frames.shape[0])
        print('a',self.frames_a.shape[0])
        print('b',self.frames_b.shape[0])

        # make a random sequence for the new spline
        sequence = self.make_sequence(spline_C.frames.shape[0])

        # minimize the new spline with the fixed frames of A and B
        self.out = self.minimize_spline(spline_C, 
                                        sequence=sequence, 
                                        closed=False, 
                                        endpoints_fixed=False, 
                                        fixed=fixed, 
                                        exvol_rad=0
                                        )

        # create a trajectory from the new spline containing both the old and new parts
        dna_c = StructureGenerator(spline_C)

        # get the trajectory of the new spline
        self.traj = dna_c.get_traj()
    

    def connect__(self,nbp=None):

        if not self.dna_b:
            raise ValueError("No second DNA sequence provided for connection.")
        
        # get the start and end of the connection
        self.get_start_and_end()

        # compute the rotation difference between the two frames (aka difference in twist per base pair)
        rotation_difference = self.get_twist_difference(self.start, self.end)

        # find optimal number of base pairs for the given range
        optimal_bps = self.find_optimal_bps(np.array([self.start[0], self.end[0]]), 
                                            bp_per_turn=10.5, 
                                            rise=0.34, 
                                            bp_range=self.bp_range, 
                                            rotation_difference=rotation_difference, 
                                            tolerance=self.tolerance, 
                                            plot=False
                                            )
        
        # get the optimal number of base pairs (smallest amount of base pairs that satisfies the tolerance)
        number_of_bp = optimal_bps[0]['optimal_bp']
        # interpolate control points for spline C
        control_points_C = self.interplotate_points(self.start[0], self.end[0], number_of_bp)
        distance = np.linalg.norm(self.start-self.end)
        spline_C = SplineFrames(control_points_C,frame_spacing=distance/len(control_points_C))
    
        # combine splines A B and C and remember the fixed nodes/frames of A and B
        # exclude first and last frame of A and B
        spline_C.frames = np.concatenate([self.frames_a[:-1],spline_C.frames,self.frames_b[1:]])

        # fix first and last 45 indices of total length of 257 frames
        fixed = list(range(self.frames_a.shape[0]-self.margin))+list(range(spline_C.frames.shape[0]-self.frames_b.shape[0]+self.margin,spline_C.frames.shape[0]))

        # make a random sequence for the new spline
        sequence = self.make_sequence(spline_C.frames.shape[0])

        # minimize the new spline with the fixed frames of A and B
        self.out = self.minimize_spline(spline_C, 
                                        sequence=sequence, 
                                        closed=False, 
                                        endpoints_fixed=False, 
                                        fixed=fixed, 
                                        exvol_rad=0
                                        )

        # create a trajectory from the new spline containing both the old and new parts
        dna_c = StructureGenerator(spline_C)

        # get the trajectory of the new spline
        self.traj = dna_c.get_traj()

    def extend(self, forward=True, nbp=None, fixed_endpoint=None):
        """Extend the DNA sequence in the specified direction using the five_end or three_end as reference.
        
        Args:
        forward: Extend the DNA sequence in the forward direction. If False, extend in the backward direction.
        nbp: Number of base pairs to extend the DNA sequence.
        fixed_endpoint: Fixed endpoint for extending the DNA sequence. This should be a orgin with a reference frame, shape (4,3).

        Returns:
        None
        """

        # extend the DNA sequence in the specified direction using the five_end or three_end as reference
        # CAREFUL ONLY WORKS NOW IN THE 3' DIRECTION!!!!

        if not nbp and not fixed_endpoint:
            raise ValueError("Either a fixed endpoint or a length must be specified for extension.")

        # get the target frame for extension
        # and normal vector of the start frame as the direction of extension
        if forward:
            start = self.get_start()
            direction = start[-1]
        else:
            start = self.get_end()
            # Flip the direction of the end frame to extend in the backward direction
            direction = -start[-1]

        # get the length of the extension
        length = nbp * 0.34 

        # get the target frame for extension
        target_frame = start[0] + direction * length
    
        # interpolate control points for the new spline
        if forward:
            control_points = self.interplotate_points(start[0], target_frame, nbp)
        else:
            control_points = self.interplotate_points(target_frame, start[0], nbp)

        # create a new spline with the interpolated control points
        spline = SplineFrames(control_points, frame_spacing=0.34)

        if forward:
            # fix the strand A except the margin at the end
            fixed = list(range(self.frames_a.shape[0]-self.margin))
        else:
            # fix the strand A but shift the fixed indices to the end
            fixed = list(range(self.frames_a.shape[0]))
            fixed = [i + nbp for i in fixed][self.margin:]
        
        # combine splines A and the new extension spline 
        if forward:
            spline.frames = np.concatenate([self.frames_a[:-1],spline.frames])
        else:
            spline.frames = np.concatenate([spline.frames,self.frames_a[1:]])

        # make a random sequence for the new spline
        sequence = self.make_sequence(spline.frames.shape[0])

        # minimize the new spline with the fixed frames of A
        self.out = self.minimize_spline(spline,
                                        sequence=sequence,
                                        closed=False,
                                        endpoints_fixed=False,
                                        fixed=fixed,
                                        exvol_rad=0
                                        )
        # create a trajectory from the new spline containing both the old and new parts
        dna = StructureGenerator(spline)

        # get the trajectory of the new spline
        self.traj = dna.get_traj()

    def get_start(self):
        if self.five_end == 'A':
            return self.frames_a[-1]
        elif self.three_end == 'A':
            return self.frames_a[0]
        else:
            raise ValueError("No starting frame found for DNA sequence A.")

    def get_end(self):
        if self.five_end == 'A':
            return self.frames_a[0]
        elif self.three_end == 'A':
            return self.frames_a[-1]
        else:
            raise ValueError("No ending frame found for DNA sequence A.")

    def get_start_and_end(self):
        if self.five_end == 'A':
            # Normally this should be -1 and 0 respectively
            self.start = self.frames_a[-1]
            self.end = self.frames_b[0]
        else:
            self.start = self.frames_b[-1]
            self.end = self.frames_a[0]

    def interplotate_points(self,start, end, n):
        return np.array([start + (end-start)*i/n for i in range(n+1)])
    
    def get_traj(self):
        # get the trajectory of the new spline
        return self.traj
    
    def make_sequence(self,n_bp):
        # make a random sequence of n_bp base pairs
        return ''.join(['ATCG'[np.random.randint(4)] for i in range(n_bp)])

    def get_pos_and_triads(self, spline):
        # get origins of the base pair frames and the triads of the base pair frames (as column vectors for each frame)
        return spline.frames[:,0,:], spline.frames[:,1:,:].transpose((0, 2, 1))

    def update_spline(self, spline, out):
        # update the spline with new positions and triads
        spline.frames[:,0,:] = out['positions'] # set the origins of the frames
        spline.frames[:,1:,:] = out['triads'].transpose((0, 2, 1))# set the triads of the frames as row vectors
        
    def minimize_spline(self,spline, fixed=[], closed=False, sequence=None, endpoints_fixed=False, exvol_rad=None):
        # get the positions and triads of the base pair frames
        pos, triads = self.get_pos_and_triads(spline)

        # start with temperature annealing at 100000K
        out  = em.equilibrate(triads,pos,sequence=sequence,closed=closed,endpoints_fixed=endpoints_fixed,fixed=fixed,temp=100000,num_cycles=100,exvol_rad=exvol_rad)
        # then do a final equilibration at 300K
        out = em.equilibrate(out['triads'],out['positions'],sequence=sequence,closed=closed,endpoints_fixed=endpoints_fixed,fixed=fixed,temp=300,exvol_rad=exvol_rad)

        # update the spline with the new positions and triads
        self.update_spline(spline, out)
        return out
    
    def get_MC_traj(self):
        """Get the MC sampling energy minimization trajectory of the new spline."""
        # Would be nice to also store the triads 
        # (or at least the vector in the direction of the backone/groove)
        # to create an extra "dummy" particle to 

        # get the xyz coordinates of the new spline
        xyz = np.array(self.out['confs'])
        # create a topology for the new spline
        topology = md.Topology()
        # add a chain to the topology
        chain = topology.add_chain()
        # add argon atoms to the topology
        for _ in range(xyz.shape[1]):
            residue = topology.add_residue(name='Ar', chain=chain)
            _atom = topology.add_atom('Ar',element=md.element.argon, residue=residue)

        # add bonds to the topology
        bonds = np.array([[i,i+1] for i in range(xyz.shape[1]-1)])
        for bond in bonds:
            topology.add_bond(topology.atom(bond[0]),topology.atom(bond[1]))

        # create a trajectory from the xyz coordinates and the topology
        test = md.Trajectory(xyz,topology=topology)
        return test
    
    def plot(self, pos, triads,ax=None):
        # plot the base pair frames
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')
        
        for position, frame in zip(pos,triads):
            right, up, forward = frame[:,0], frame[:,1], frame[:,2]
            ax.quiver(*position, *right, length=0.2, color='g')
            ax.quiver(*position, *up, length=0.2, color='b')
            ax.quiver(*position, *forward, length=0.2, color='r')

        ax.plot(*pos.T, color='black', label='Control Points',lw=1)
        ax.axis('equal')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.legend()

    def plot_frames(self, spline,ax=None):
        # get the positions and triads of the base pair frames
        pos, triads = self.get_pos_and_triads(spline)
        # plot the base pair frames
        self.plot(pos, triads, ax=ax)

    def find_minima(self, lst):
        """Finds the indices of local minima in a list."""
        return [i for i in range(1, len(lst) - 1) if lst[i - 1] > lst[i] and lst[i + 1] > lst[i]]

    def compute_left_over(self, bp_range, min_bp, bp_per_turn, rotation_difference):
        """Computes the left-over rotational difference for a range of base pairs."""
        cumul_twist = np.arange(min_bp, min_bp + bp_range) * 360 / bp_per_turn
        return cumul_twist % 360 - rotation_difference

    def compute_twist_diff_per_bp(self, optimal_bp, left_over, min_bp):
        """Calculates the twist difference per base pair for an optimal base pair number."""
        total_twist_diff = left_over[optimal_bp - min_bp]
        return total_twist_diff / optimal_bp

    def check_within_tolerance(self, twist_diff_per_bp, tolerance):
        """Checks if the twist difference per base pair is within the specified tolerance."""
        return np.abs(twist_diff_per_bp) < tolerance

    def plot_leftover(self, min_bp,left_over):
        # Plotting the left-over rotational differences
        plt.plot(np.arange(min_bp, min_bp + len(left_over)), np.abs(left_over))
        plt.xlabel('Number of Base Pairs')
        plt.ylabel('Absolute Left Over')
        plt.show()

    def find_optimal_bps(self, positions, bp_per_turn, rise, bp_range, rotation_difference, tolerance, plot=False):
        """Finds optimal base pairs that satisfy the given tolerance.

        Args:
        positions: The positions of base pairs.
        bp_per_turn: Base pairs per turn.
        rise: Component of arc length.
        bp_range: Range of base pairs to consider.
        rotation_difference: The target rotation difference.
        tolerance: The tolerance for accepting an optimal base pair number.
        plot: If True, plots the left-over rotational differences.

        Returns:
        A list of dictionaries containing optimal base pair numbers and their twist differences per base pair.
        """
        min_arc = np.linalg.norm(positions[0] - positions[-1])
        min_bp = int(np.ceil(min_arc / rise))
        left_over = self.compute_left_over(bp_range, min_bp, bp_per_turn, rotation_difference)
        
        if plot:
            self.plot_leftover(min_bp,left_over)

        minima = self.find_minima(np.abs(left_over))
        results = []

        for min_val in minima:
            optimal_bp = min_bp + min_val
            twist_diff_per_bp = self.compute_twist_diff_per_bp(optimal_bp, left_over, min_bp)
            if self.check_within_tolerance(twist_diff_per_bp, tolerance):
                results.append({
                    'optimal_bp': optimal_bp ,
                    'twist_diff_per_bp': np.round(twist_diff_per_bp, 3)
                })
        if len(results) > 0:
            for result in results[:1]:
                print(f'Optimal BP: {result["optimal_bp"]}, Twist Difference per BP: {result["twist_diff_per_bp"]} degrees')
        else:
            print("No optimal number of base pairs found within the specified tolerance.")
        return results

    def compute_euler_angles(self, frame_A, frame_B):
        # Compute the rotation matrix R that transforms frame A to frame B
        rotation_matrix = np.dot(frame_B.T, frame_A)
        
        # Create a rotation object from the rotation matrix
        rotation = R.from_matrix(rotation_matrix)
        
        # Convert the rotation to Euler angles (ZYX convention)
        euler_angles = rotation.as_euler('zyx', degrees=True)
        
        # Return the Euler angles: yaw (Z), pitch (Y), and roll (X)
        return euler_angles

    def get_twist_difference(self, frame_a, frame_b):
        """Calculates the twist difference between two frames."""
        
        b1 = frame_a[1:]/np.linalg.norm(frame_a[1:])
        b2 = frame_b[1:]/np.linalg.norm(frame_b[1:])

        euler_angles = self.compute_euler_angles(b1, b2)
        return euler_angles[-1]


class Build_spline:

    def __init__(self, dna_a, dna_b=None, five_end='A', three_end='B', margin=1):
        self.dna_a = dna_a
        self.dna_b = dna_b
        self.frames_a = dna_a.frames if dna_a else None
        self.frames_b = dna_b.frames if dna_b else None
        self.five_end = five_end 
        self.three_end = three_end
        self.margin = margin
        self.bp_range = 100 # should double check what this does again
        self.tolerance = np.abs((360 / 10.4) - (360 / 10.6))

    def equilibrate(self, sequence=None, closed=False, endpoints_fixed=False, fixed=[]):

        # make a random seque`nce for the new spline
        if sequence is None:
            sequence = self.dna_a.sequence

        # minimize the new spline with the fixed frames of A and B
        self.out = self.minimize_spline(self.dna_a.spline, 
                                        sequence=sequence, 
                                        closed=closed, 
                                        endpoints_fixed=False, 
                                        fixed=fixed, 
                                        exvol_rad=0
                                        )
        

        dna = StructureGenerator(self.dna_a.spline,sequence=sequence)
        return dna 

    def connect(self,nbp=None, control_points=None,index=0):

        if not self.dna_b:
            raise ValueError("No second DNA sequence provided for connection.")
        
        # get the start and end of the connection
        self.get_start_and_end()

        # compute the rotation difference between the two frames (aka difference in twist per base pair)
        rotation_difference = self.get_twist_difference(self.start, self.end)

        if nbp is None:
            # find optimal number of base pairs for the given range
            optimal_bps = self.find_optimal_bps(np.array([self.start[0], self.end[0]]), 
                                                bp_per_turn=10.5, 
                                                rise=0.34, 
                                                bp_range=self.bp_range, 
                                                rotation_difference=rotation_difference, 
                                                tolerance=self.tolerance, 
                                                plot=False
                                                )
            
            # get the optimal number of base pairs (smallest amount of base pairs that satisfies the tolerance)
            number_of_bp = optimal_bps[index]['optimal_bp']
        else:
            number_of_bp = nbp
        
        # interpolate control points for spline C
        if control_points is None:
            control_points_C = self.interplotate_points(self.start[0], self.end[0], number_of_bp)
            distance = np.linalg.norm(self.start-self.end)
            self.control_points_C = control_points_C    
            spline_C = SplineFrames(control_points_C,frame_spacing=distance/len(control_points_C))
        else:
            control_points_C = control_points
            self.control_points_C = control_points_C   
            spline_C = SplineFrames(control_points_C,frame_spacing=0.34, initial_frame=self.start)

    
        # combine splines A B and C and remember the fixed nodes/frames of A and B
        # exclude first and last frame of A and B
        spline_C.frames = np.concatenate([self.frames_a[:-1],spline_C.frames,self.frames_b[1:]])
        self.spline_C_raw = copy.deepcopy(spline_C)
        # fix first and last 45 indices of total length of 257 frames
        fixed = list(range(self.frames_a.shape[0]-self.margin))+list(range(spline_C.frames.shape[0]-self.frames_b.shape[0]+self.margin,spline_C.frames.shape[0]))
        print('f',fixed)
        print('c',spline_C.frames.shape[0])
        print('a',self.frames_a.shape[0])
        print('b',self.frames_b.shape[0])

        # make a random sequence for the new spline
        sequence = self.make_sequence(spline_C.frames.shape[0])

        # minimize the new spline with the fixed frames of A and B
        self.out = self.minimize_spline(spline_C, 
                                        sequence=sequence, 
                                        closed=False, 
                                        endpoints_fixed=False, 
                                        fixed=fixed, 
                                        exvol_rad=0
                                        )

        # create a trajectory from the new spline containing both the old and new parts
        dna_c = StructureGenerator(spline_C)

        # get the trajectory of the new spline
        self.traj = dna_c.get_traj()
    

    def connect__(self,nbp=None):

        if not self.dna_b:
            raise ValueError("No second DNA sequence provided for connection.")
        
        # get the start and end of the connection
        self.get_start_and_end()

        # compute the rotation difference between the two frames (aka difference in twist per base pair)
        rotation_difference = self.get_twist_difference(self.start, self.end)

        # find optimal number of base pairs for the given range
        optimal_bps = self.find_optimal_bps(np.array([self.start[0], self.end[0]]), 
                                            bp_per_turn=10.5, 
                                            rise=0.34, 
                                            bp_range=self.bp_range, 
                                            rotation_difference=rotation_difference, 
                                            tolerance=self.tolerance, 
                                            plot=False
                                            )
        
        # get the optimal number of base pairs (smallest amount of base pairs that satisfies the tolerance)
        number_of_bp = optimal_bps[0]['optimal_bp']
        # interpolate control points for spline C
        control_points_C = self.interplotate_points(self.start[0], self.end[0], number_of_bp)
        distance = np.linalg.norm(self.start-self.end)
        spline_C = SplineFrames(control_points_C,frame_spacing=distance/len(control_points_C))
    
        # combine splines A B and C and remember the fixed nodes/frames of A and B
        # exclude first and last frame of A and B
        spline_C.frames = np.concatenate([self.frames_a[:-1],spline_C.frames,self.frames_b[1:]])

        # fix first and last 45 indices of total length of 257 frames
        fixed = list(range(self.frames_a.shape[0]-self.margin))+list(range(spline_C.frames.shape[0]-self.frames_b.shape[0]+self.margin,spline_C.frames.shape[0]))

        # make a random sequence for the new spline
        sequence = self.make_sequence(spline_C.frames.shape[0])

        # minimize the new spline with the fixed frames of A and B
        self.out = self.minimize_spline(spline_C, 
                                        sequence=sequence, 
                                        closed=False, 
                                        endpoints_fixed=False, 
                                        fixed=fixed, 
                                        exvol_rad=0
                                        )

        # create a trajectory from the new spline containing both the old and new parts
        dna_c = StructureGenerator(spline_C)

        # get the trajectory of the new spline
        self.traj = dna_c.get_traj()

    def extend(self, forward=True, nbp=None, fixed_endpoint=None):
        """Extend the DNA sequence in the specified direction using the five_end or three_end as reference.
        
        Args:
        forward: Extend the DNA sequence in the forward direction. If False, extend in the backward direction.
        nbp: Number of base pairs to extend the DNA sequence.
        fixed_endpoint: Fixed endpoint for extending the DNA sequence. This should be a orgin with a reference frame, shape (4,3).

        Returns:
        None
        """

        # extend the DNA sequence in the specified direction using the five_end or three_end as reference
        # CAREFUL ONLY WORKS NOW IN THE 3' DIRECTION!!!!

        if not nbp and not fixed_endpoint:
            raise ValueError("Either a fixed endpoint or a length must be specified for extension.")

        # get the target frame for extension
        # and normal vector of the start frame as the direction of extension
        if forward:
            start = self.get_start()
            direction = start[-1]
        else:
            start = self.get_end()
            # Flip the direction of the end frame to extend in the backward direction
            direction = -start[-1]

        # get the length of the extension
        length = nbp * 0.34 

        # get the target frame for extension
        target_frame = start[0] + direction * length
    
        # interpolate control points for the new spline
        if forward:
            control_points = self.interplotate_points(start[0], target_frame, nbp)
        else:
            control_points = self.interplotate_points(target_frame, start[0], nbp)

        # create a new spline with the interpolated control points
        spline = SplineFrames(control_points, frame_spacing=0.34)

        if forward:
            # fix the strand A except the margin at the end
            fixed = list(range(self.frames_a.shape[0]-self.margin))
        else:
            # fix the strand A but shift the fixed indices to the end
            fixed = list(range(self.frames_a.shape[0]))
            fixed = [i + nbp for i in fixed][self.margin:]
        
        # combine splines A and the new extension spline 
        if forward:
            spline.frames = np.concatenate([self.frames_a[:-1],spline.frames])
        else:
            spline.frames = np.concatenate([spline.frames,self.frames_a[1:]])

        # make a random sequence for the new spline
        sequence = self.make_sequence(spline.frames.shape[0])

        # minimize the new spline with the fixed frames of A
        self.out = self.minimize_spline(spline,
                                        sequence=sequence,
                                        closed=False,
                                        endpoints_fixed=False,
                                        fixed=fixed,
                                        exvol_rad=0
                                        )
        # create a trajectory from the new spline containing both the old and new parts
        dna = StructureGenerator(spline)

        # get the trajectory of the new spline
        self.traj = dna.get_traj()

    def get_start(self):
        if self.five_end == 'A':
            return self.frames_a[-1]
        elif self.three_end == 'A':
            return self.frames_a[0]
        else:
            raise ValueError("No starting frame found for DNA sequence A.")

    def get_end(self):
        if self.five_end == 'A':
            return self.frames_a[0]
        elif self.three_end == 'A':
            return self.frames_a[-1]
        else:
            raise ValueError("No ending frame found for DNA sequence A.")

    def get_start_and_end(self):
        if self.five_end == 'A':
            # Normally this should be -1 and 0 respectively
            self.start = self.frames_a[-1]
            self.end = self.frames_b[0]
        else:
            self.start = self.frames_b[-1]
            self.end = self.frames_a[0]

    def interplotate_points(self,start, end, n):
        return np.array([start + (end-start)*i/n for i in range(n+1)])
    
    def get_traj(self):
        # get the trajectory of the new spline
        return self.traj
    
    def make_sequence(self,n_bp):
        # make a random sequence of n_bp base pairs
        return ''.join(['ATCG'[np.random.randint(4)] for i in range(n_bp)])

    def get_pos_and_triads(self, spline):
        # get origins of the base pair frames and the triads of the base pair frames (as column vectors for each frame)
        return spline.frames[:,0,:], spline.frames[:,1:,:].transpose((0, 2, 1))

    def update_spline(self, spline, out):
        # update the spline with new positions and triads
        spline.frames[:,0,:] = out['positions'] # set the origins of the frames
        spline.frames[:,1:,:] = out['triads'].transpose((0, 2, 1))# set the triads of the frames as row vectors
        
    def minimize_spline(self,spline, fixed=[], closed=False, sequence=None, endpoints_fixed=False, exvol_rad=None):
        # get the positions and triads of the base pair frames
        pos, triads = self.get_pos_and_triads(spline)

        # start with temperature annealing at 100000K
        out  = em.equilibrate(triads,pos,sequence=sequence,closed=closed,endpoints_fixed=endpoints_fixed,fixed=fixed,temp=100000,num_cycles=100,exvol_rad=exvol_rad)
        # then do a final equilibration at 300K
        out = em.equilibrate(out['triads'],out['positions'],sequence=sequence,closed=closed,endpoints_fixed=endpoints_fixed,fixed=fixed,temp=300,exvol_rad=exvol_rad)

        # update the spline with the new positions and triads
        self.update_spline(spline, out)
        return out
    
    def get_MC_traj(self):
        """Get the MC sampling energy minimization trajectory of the new spline."""
        # Would be nice to also store the triads 
        # (or at least the vector in the direction of the backone/groove)
        # to create an extra "dummy" particle to 

        # get the xyz coordinates of the new spline
        xyz = np.array(self.out['confs'])
        # create a topology for the new spline
        topology = md.Topology()
        # add a chain to the topology
        chain = topology.add_chain()
        # add argon atoms to the topology
        for _ in range(xyz.shape[1]):
            residue = topology.add_residue(name='Ar', chain=chain)
            _atom = topology.add_atom('Ar',element=md.element.argon, residue=residue)

        # add bonds to the topology
        bonds = np.array([[i,i+1] for i in range(xyz.shape[1]-1)])
        for bond in bonds:
            topology.add_bond(topology.atom(bond[0]),topology.atom(bond[1]))

        # create a trajectory from the xyz coordinates and the topology
        test = md.Trajectory(xyz,topology=topology)
        return test
    
    def plot(self, pos, triads,ax=None):
        # plot the base pair frames
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')
        
        for position, frame in zip(pos,triads):
            right, up, forward = frame[:,0], frame[:,1], frame[:,2]
            ax.quiver(*position, *right, length=0.2, color='g')
            ax.quiver(*position, *up, length=0.2, color='b')
            ax.quiver(*position, *forward, length=0.2, color='r')

        ax.plot(*pos.T, color='black', label='Control Points',lw=1)
        ax.axis('equal')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.legend()

    def plot_frames(self, spline,ax=None):
        # get the positions and triads of the base pair frames
        pos, triads = self.get_pos_and_triads(spline)
        # plot the base pair frames
        self.plot(pos, triads, ax=ax)

    def find_minima(self, lst):
        """Finds the indices of local minima in a list."""
        return [i for i in range(1, len(lst) - 1) if lst[i - 1] > lst[i] and lst[i + 1] > lst[i]]

    def compute_left_over(self, bp_range, min_bp, bp_per_turn, rotation_difference):
        """Computes the left-over rotational difference for a range of base pairs."""
        cumul_twist = np.arange(min_bp, min_bp + bp_range) * 360 / bp_per_turn
        return cumul_twist % 360 - rotation_difference

    def compute_twist_diff_per_bp(self, optimal_bp, left_over, min_bp):
        """Calculates the twist difference per base pair for an optimal base pair number."""
        total_twist_diff = left_over[optimal_bp - min_bp]
        return total_twist_diff / optimal_bp

    def check_within_tolerance(self, twist_diff_per_bp, tolerance):
        """Checks if the twist difference per base pair is within the specified tolerance."""
        return np.abs(twist_diff_per_bp) < tolerance

    def plot_leftover(self, min_bp,left_over):
        # Plotting the left-over rotational differences
        plt.plot(np.arange(min_bp, min_bp + len(left_over)), np.abs(left_over))
        plt.xlabel('Number of Base Pairs')
        plt.ylabel('Absolute Left Over')
        plt.show()

    def find_optimal_bps(self, positions, bp_per_turn, rise, bp_range, rotation_difference, tolerance, plot=False):
        """Finds optimal base pairs that satisfy the given tolerance.

        Args:
        positions: The positions of base pairs.
        bp_per_turn: Base pairs per turn.
        rise: Component of arc length.
        bp_range: Range of base pairs to consider.
        rotation_difference: The target rotation difference.
        tolerance: The tolerance for accepting an optimal base pair number.
        plot: If True, plots the left-over rotational differences.

        Returns:
        A list of dictionaries containing optimal base pair numbers and their twist differences per base pair.
        """
        min_arc = np.linalg.norm(positions[0] - positions[-1])
        min_bp = int(np.ceil(min_arc / rise))
        left_over = self.compute_left_over(bp_range, min_bp, bp_per_turn, rotation_difference)
        
        if plot:
            self.plot_leftover(min_bp,left_over)

        minima = self.find_minima(np.abs(left_over))
        results = []

        for min_val in minima:
            optimal_bp = min_bp + min_val
            twist_diff_per_bp = self.compute_twist_diff_per_bp(optimal_bp, left_over, min_bp)
            if self.check_within_tolerance(twist_diff_per_bp, tolerance):
                results.append({
                    'optimal_bp': optimal_bp ,
                    'twist_diff_per_bp': np.round(twist_diff_per_bp, 3)
                })
        if len(results) > 0:
            for result in results[:1]:
                print(f'Optimal BP: {result["optimal_bp"]}, Twist Difference per BP: {result["twist_diff_per_bp"]} degrees')
        else:
            print("No optimal number of base pairs found within the specified tolerance.")
        return results

    def compute_euler_angles(self, frame_A, frame_B):
        # Compute the rotation matrix R that transforms frame A to frame B
        rotation_matrix = np.dot(frame_B.T, frame_A)
        
        # Create a rotation object from the rotation matrix
        rotation = R.from_matrix(rotation_matrix)
        
        # Convert the rotation to Euler angles (ZYX convention)
        euler_angles = rotation.as_euler('zyx', degrees=True)
        
        # Return the Euler angles: yaw (Z), pitch (Y), and roll (X)
        return euler_angles

    def get_twist_difference(self, frame_a, frame_b):
        """Calculates the twist difference between two frames."""
        
        b1 = frame_a[1:]/np.linalg.norm(frame_a[1:])
        b2 = frame_b[1:]/np.linalg.norm(frame_b[1:])

        euler_angles = self.compute_euler_angles(b1, b2)
        return euler_angles[-1]


class Build___:

    def __init__(self, dna_a, dna_b=None, five_end='A', three_end='B', margin=1):
        # options for input 
        # dna: StructureGenerator object
        # dna: frames and sequence object
        # dna: mdtraj trajectory object and frame number
        
        self.dna_a = dna_a
        self.dna_b = dna_b
        self.five_end = five_end 
        self.three_end = three_end
        self.margin = margin
        self.bp_range = 100 # should double check what this does again
        self.tolerance = np.abs((360 / 10.4) - (360 / 10.6))
    
    def get_spline_and_frames(self, dna):
        nuc = NucleicFrames(dna)
        frames = np.squeeze(nuc.mean_reference_frames)
        spline = StructureGenerator(frames)
        return frames, spline


    def equilibrate(self, sequence=None, closed=False, endpoints_fixed=False, fixed=[]):

        # make a random sequence for the new spline
        if sequence is None:
            sequence = self.dna_a.sequence

        # minimize the new spline with the fixed frames of A and B
        self.out = self.minimize_spline(self.dna_a.spline, 
                                        sequence=sequence, 
                                        closed=closed, 
                                        endpoints_fixed=False, 
                                        fixed=fixed, 
                                        exvol_rad=0
                                        )
        

        dna = StructureGenerator(self.dna_a.spline,sequence=sequence)
        return dna 

    def connect(self):

        if not self.dna_b:
            raise ValueError("No second DNA sequence provided for connection.")
        
        # get the start and end of the connection
        self.get_start_and_end()

        # compute the rotation difference between the two frames (aka difference in twist per base pair)
        rotation_difference = self.get_twist_difference(self.start, self.end)

        # find optimal number of base pairs for the given range
        optimal_bps = self.find_optimal_bps(np.array([self.start[0], self.end[0]]), 
                                            bp_per_turn=10.5, 
                                            rise=0.34, 
                                            bp_range=self.bp_range, 
                                            rotation_difference=rotation_difference, 
                                            tolerance=self.tolerance, 
                                            plot=False
                                            )
        
        # get the optimal number of base pairs (smallest amount of base pairs that satisfies the tolerance)
        number_of_bp = optimal_bps[0]['optimal_bp']
        
        # interpolate control points for spline C
        control_points_C = self.interplotate_points(self.start[0], self.end[0], number_of_bp)
        distance = np.linalg.norm(self.start-self.end)
        spline_C = SplineFrames(control_points_C,frame_spacing=distance/len(control_points_C))
    
        # combine splines A B and C and remember the fixed nodes/frames of A and B
        # exclude first and last frame of A and B
        spline_C.frames = np.concatenate([self.frames_a[:-1],spline_C.frames,self.frames_b[1:]])

        # fix first and last 45 indices of total length of 257 frames
        fixed = list(range(self.frames_a.shape[0]-self.margin))+list(range(spline_C.frames.shape[0]-self.frames_b.shape[0]+self.margin,spline_C.frames.shape[0]))

        # make a random sequence for the new spline
        sequence = self.make_sequence(spline_C.frames.shape[0])

        # minimize the new spline with the fixed frames of A and B
        self.out = self.minimize_spline(spline_C, 
                                        sequence=sequence, 
                                        closed=False, 
                                        endpoints_fixed=False, 
                                        fixed=fixed, 
                                        exvol_rad=0
                                        )

        # create a trajectory from the new spline containing both the old and new parts
        dna_c = StructureGenerator(spline_C)

        # get the trajectory of the new spline
        self.traj = dna_c.get_traj()
    
    def extend(self, nbp=None, fixed_endpoint=None):
        # extend the DNA sequence in the specified direction using the five_end or three_end as reference
        # CAREFUL ONLY WORKS NOW IN THE 3' DIRECTION!!!!

        if not nbp and not fixed_endpoint:
            raise ValueError("Either a fixed endpoint or a length must be specified for extension.")

        # get the target frame for extension
        start = self.get_start()
        # get normal vector of the start frame as the direction of extension
        direction = start[-1]
        # get the length of the extension
        length = nbp * 0.34 

        # get the target frame for extension
        target_frame = start[0] + direction * length
    
        # interpolate control points for the new spline
        control_points = self.interplotate_points(start[0], target_frame, nbp)

        # create a new spline with the interpolated control points
        spline = SplineFrames(control_points, frame_spacing=0.34)

        # fix the strand A except the margin at the end
        fixed = list(range(self.frames_a.shape[0]-self.margin))
        
        # combine splines A and the new extension spline 
        spline.frames = np.concatenate([self.frames_a[:-1],spline.frames])

        # make a random sequence for the new spline
        sequence = self.make_sequence(spline.frames.shape[0])

        # minimize the new spline with the fixed frames of A
        self.out = self.minimize_spline(spline,
                                        sequence=sequence,
                                        closed=False,
                                        endpoints_fixed=False,
                                        fixed=fixed,
                                        exvol_rad=0
                                        )
        # create a trajectory from the new spline containing both the old and new parts
        dna = StructureGenerator(spline)

        # get the trajectory of the new spline
        self.traj = dna.get_traj()

    def get_start(self):
        if self.five_end == 'A':
            return self.frames_a[-1]
        elif self.three_end == 'A':
            return self.frames_a[0]
        else:
            raise ValueError("No starting frame found for DNA sequence A.")

    def get_start_and_end(self):
        if self.five_end == 'A':
            self.start = self.frames_a[-1]
            self.end = self.frames_b[0]
        else:
            self.start = self.frames_b[-1]
            self.end = self.frames_a[0]

    def interplotate_points(self,start, end, n):
        return np.array([start + (end-start)*i/n for i in range(n+1)])
    
    def get_traj(self):
        # get the trajectory of the new spline
        return self.traj
    
    def make_sequence(self,n_bp):
        # make a random sequence of n_bp base pairs
        return ''.join(['ATCG'[np.random.randint(4)] for i in range(n_bp)])

    def get_pos_and_triads(self, spline):
        # get origins of the base pair frames and the triads of the base pair frames (as column vectors for each frame)
        return spline.frames[:,0,:], spline.frames[:,1:,:].transpose((0, 2, 1))

    def update_spline(self, spline, out):
        # update the spline with new positions and triads
        spline.frames[:,0,:] = out['positions'] # set the origins of the frames
        spline.frames[:,1:,:] = out['triads'].transpose((0, 2, 1))# set the triads of the frames as row vectors
        
    def minimize_spline(self,spline, fixed=[], closed=False, sequence=None, endpoints_fixed=False, exvol_rad=0):
        # get the positions and triads of the base pair frames
        pos, triads = self.get_pos_and_triads(spline)

        # start with temperature annealing at 100000K
        out  = em.equilibrate(triads,pos,sequence=sequence,closed=closed,endpoints_fixed=endpoints_fixed,fixed=fixed,temp=100000,num_cycles=100,exvol_rad=exvol_rad)
        # then do a final equilibration at 300K
        out = em.equilibrate(out['triads'],out['positions'],sequence=sequence,closed=closed,endpoints_fixed=endpoints_fixed,fixed=fixed,temp=300,exvol_rad=exvol_rad)

        # update the spline with the new positions and triads
        self.update_spline(spline, out)
        return out
    
    def get_MC_traj(self):
        """Get the MC sampling energy minimization trajectory of the new spline."""
        # Would be nice to also store the triads 
        # (or at least the vector in the direction of the backone/groove)
        # to create an extra "dummy" particle to 

        # get the xyz coordinates of the new spline
        xyz = np.array(self.out['confs'])
        # create a topology for the new spline
        topology = md.Topology()
        # add a chain to the topology
        chain = topology.add_chain()
        # add argon atoms to the topology
        for _ in range(xyz.shape[1]):
            residue = topology.add_residue(name='Ar', chain=chain)
            atom = topology.add_atom('Ar',element=md.element.argon, residue=residue)

        # add bonds to the topology
        bonds = np.array([[i,i+1] for i in range(xyz.shape[1]-1)])
        for bond in bonds:
            topology.add_bond(topology.atom(bond[0]),topology.atom(bond[1]))

        # create a trajectory from the xyz coordinates and the topology
        test = md.Trajectory(xyz,topology=topology)
        return test
    
    def plot(self, pos, triads,ax=None):
        # plot the base pair frames
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')
        
        for position, frame in zip(pos,triads):
            right, up, forward = frame[:,0], frame[:,1], frame[:,2]
            ax.quiver(*position, *right, length=0.2, color='g')
            ax.quiver(*position, *up, length=0.2, color='b')
            ax.quiver(*position, *forward, length=0.2, color='r')

        ax.plot(*pos.T, color='black', label='Control Points',lw=1)
        ax.axis('equal')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.legend()

    def plot_frames(self, spline,ax=None):
        # get the positions and triads of the base pair frames
        pos, triads = self.get_pos_and_triads(spline)
        # plot the base pair frames
        self.plot(pos, triads, ax=ax)

    def find_minima(self, lst):
        """Finds the indices of local minima in a list."""
        return [i for i in range(1, len(lst) - 1) if lst[i - 1] > lst[i] and lst[i + 1] > lst[i]]

    def compute_left_over(self, bp_range, min_bp, bp_per_turn, rotation_difference):
        """Computes the left-over rotational difference for a range of base pairs."""
        cumul_twist = np.arange(min_bp, min_bp + bp_range) * 360 / bp_per_turn
        return cumul_twist % 360 - rotation_difference

    def compute_twist_diff_per_bp(self, optimal_bp, left_over, min_bp):
        """Calculates the twist difference per base pair for an optimal base pair number."""
        total_twist_diff = left_over[optimal_bp - min_bp]
        return total_twist_diff / optimal_bp

    def check_within_tolerance(self, twist_diff_per_bp, tolerance):
        """Checks if the twist difference per base pair is within the specified tolerance."""
        return np.abs(twist_diff_per_bp) < tolerance

    def plot_leftover(self, min_bp,left_over):
        # Plotting the left-over rotational differences
        plt.plot(np.arange(min_bp, min_bp + len(left_over)), np.abs(left_over))
        plt.xlabel('Number of Base Pairs')
        plt.ylabel('Absolute Left Over')
        plt.show()

    def find_optimal_bps(self, positions, bp_per_turn, rise, bp_range, rotation_difference, tolerance, plot=False):
        """Finds optimal base pairs that satisfy the given tolerance.

        Args:
        positions: The positions of base pairs.
        bp_per_turn: Base pairs per turn.
        rise: Component of arc length.
        bp_range: Range of base pairs to consider.
        rotation_difference: The target rotation difference.
        tolerance: The tolerance for accepting an optimal base pair number.
        plot: If True, plots the left-over rotational differences.

        Returns:
        A list of dictionaries containing optimal base pair numbers and their twist differences per base pair.
        """
        min_arc = np.linalg.norm(positions[0] - positions[-1])
        min_bp = int(np.ceil(min_arc / rise))
        left_over = self.compute_left_over(bp_range, min_bp, bp_per_turn, rotation_difference)
        
        if plot:
            self.plot_leftover(min_bp,left_over)

        minima = self.find_minima(np.abs(left_over))
        results = []

        for min_val in minima:
            optimal_bp = min_bp + min_val
            twist_diff_per_bp = self.compute_twist_diff_per_bp(optimal_bp, left_over, min_bp)
            if self.check_within_tolerance(twist_diff_per_bp, tolerance):
                results.append({
                    'optimal_bp': optimal_bp ,
                    'twist_diff_per_bp': np.round(twist_diff_per_bp, 3)
                })
        if len(results) > 0:
            for result in results[:1]:
                print(f'Optimal BP: {result["optimal_bp"]}, Twist Difference per BP: {result["twist_diff_per_bp"]} degrees')
        else:
            print("No optimal number of base pairs found within the specified tolerance.")
        return results

    def compute_euler_angles(self, frame_A, frame_B):
        # Compute the rotation matrix R that transforms frame A to frame B
        rotation_matrix = np.dot(frame_B.T, frame_A)
        
        # Create a rotation object from the rotation matrix
        rotation = R.from_matrix(rotation_matrix)
        
        # Convert the rotation to Euler angles (ZYX convention)
        euler_angles = rotation.as_euler('zyx', degrees=True)
        
        # Return the Euler angles: yaw (Z), pitch (Y), and roll (X)
        return euler_angles

    def get_twist_difference(self, frame_a, frame_b):
        """Calculates the twist difference between two frames."""
        
        b1 = frame_a[1:]/np.linalg.norm(frame_a[1:])
        b2 = frame_b[1:]/np.linalg.norm(frame_b[1:])

        euler_angles = self.compute_euler_angles(b1, b2)
        return euler_angles[-1]

    


# # create main
# if __name__ == "__main__":
#     # create instances of Connect class
#     dna_a = ...
#     dna_b = ...
#     builder = Build(dna_a, dna_b)
#     # get the MC sampling energy minimization trajectory
#     mc_traj = builder.get_MC_traj()
#     # get the trajectory of the new spline
#     traj = builder.get_traj()
#     # plot the frames of the new spline
#     builder.plot_frames(traj)