
import numpy as N
from fieldoperations import FieldOperations
import util
import parallel

class BPOD(object):
    """Balanced Proper Orthogonal Decomposition
    
    Computes direct and adjoint modes from direct and adjoint fields.
    It uses FieldOperations for low level functions.
    
    Usage::
    
      myBPOD = BPOD(get_field=my_get_field, put_field=my_put_field,
          inner_product=my_inner_product, max_fields_per_node=500)
      myBPOD.compute_decomp(direct_field_paths, adjoint_field_paths)      
      myBPOD.compute_direct_modes(range(1, 50), 'bpod_direct_mode_%03d.txt')
      myBPOD.compute_adjoint_modes(range(1, 50), 'bpod_adjoint_mode_%03d.txt')
    """
    
    def __init__(self, get_field=None, put_field=None, 
        save_mat=util.save_mat_text, load_mat=util.load_mat_text,
        inner_product=None, max_fields_per_node=2, verbose=True):
        """Constructor
        
        Kwargs:
            get_field: Function to get a field from elsewhere (memory or a file).
            
            put_field: Function to put a field elsewhere (to memory or a file).
            
            save_mat: Function to save a matrix.
            
            inner_product: Function to take inner product of two fields.
            
            verbose: print more information about progress and warnings
        """
        # Class that contains all of the low-level field operations
        # and parallelizes them.
        self.field_ops = FieldOperations(get_field=get_field, 
            put_field=put_field, inner_product=inner_product, 
            max_fields_per_node=max_fields_per_node, verbose=verbose)
        self.parallel = parallel.default_instance

        self.load_mat = load_mat
        self.save_mat = save_mat
        self.verbose = verbose
 

    def load_decomp(self, L_sing_vecs_path, sing_vals_path, R_sing_vecs_path):
        """Loads the decomposition matrices from file. 
        """
        if self.load_mat is None:
            raise UndefinedError('Must specify a load_mat function')
        if self.parallel.is_rank_zero():
            self.L_sing_vecs = self.load_mat(L_sing_vecs_path)
            self.sing_vals = N.squeeze(N.array(self.load_mat(sing_vals_path)))
            self.R_sing_vecs = self.load_mat(R_sing_vecs_path)
        else:
            self.L_sing_vecs = None
            self.sing_vals = None
            self.R_sing_vecs = None
        if self.parallel.is_distributed():
            self.L_sing_vecs = self.parallel.comm.bcast(self.L_sing_vecs, root=0)
            self.sing_vals = self.parallel.comm.bcast(self.sing_vals, root=0)
            self.R_sing_vecs = self.parallel.comm.bcast(self.L_sing_vecs, root=0)
    
    
    def save_hankel_mat(self, hankel_mat_path):
        if self.save_mat is None:
            raise util.UndefinedError('save_mat not specified')
        elif self.parallel.is_rank_zero():
            self.save_mat(self.hankel_mat, hankel_mat_path)           
    
    
    def save_L_sing_vecs(self, path):
        if self.save_mat is None:
            raise util.UndefinedError("save_mat not specified")
        elif self.parallel.is_rank_zero():
            self.save_mat(self.L_sing_vecs, path)
        
    def save_R_sing_vecs(self, path):
        if self.save_mat is None:
            raise util.UndefinedError("save_mat not specified")
        elif self.parallel.is_rank_zero():
            self.save_mat(self.R_sing_vecs, path)
    
    def save_sing_vals(self, path):
        if self.save_mat is None:
            raise util.UndefinedError("save_mat not specified")
        elif self.parallel.is_rank_zero():
            self.save_mat(self.sing_vals, path)
   
    
    def save_decomp(self, L_sing_vecs_path, sing_vals_path, R_sing_vecs_path):
        """Save the decomposition matrices to file."""
        self.save_L_sing_vecs(L_sing_vecs_path)
        self.save_R_sing_vecs(R_sing_vecs_path)
        self.save_sing_vals(sing_vals_path)
        
        
    def compute_decomp(self, direct_field_paths, adjoint_field_paths):
        """Compute BPOD from given fields.
        
        Computes the Hankel mat Y*X, then takes the SVD of this matrix.
        """        
        self.direct_field_paths = direct_field_paths
        self.adjoint_field_paths = adjoint_field_paths
        # Do Y.conj()*X
        self.hankel_mat = self.field_ops.compute_inner_product_mat(
            self.adjoint_field_paths, self.direct_field_paths)
        self.compute_SVD()        
        #self.parallel.evaluate_and_bcast([self.L_sing_vecs,self.sing_vals,self.\
        #    R_sing_vecs], util.svd, arguments = [self.hankel_mat])


    def compute_SVD(self):
        """Takes the SVD of the Hankel matrix.
        
        This is useful if you already have the Hankel mat and want to skip 
        compute_decomp. 
        Set self.hankel_mat, and call this function.
        """
        if self.parallel.is_rank_zero():
            self.L_sing_vecs, self.sing_vals, self.R_sing_vecs = \
                util.svd(self.hankel_mat)
        else:
            self.L_sing_vecs = None
            self.R_sing_vecs = None
            self.sing_vals = None
        if self.parallel.is_distributed():
            self.L_sing_vecs = self.parallel.comm.bcast(self.L_sing_vecs, root=0)
            self.sing_vals = self.parallel.comm.bcast(self.sing_vals, root=0)
            self.R_sing_vecs = self.parallel.comm.bcast(self.R_sing_vecs, root=0)
        

    def compute_direct_modes(self, mode_nums, mode_path, index_from=1,
        direct_field_paths=None):
        """Computes the direct modes and calls ``self.self.put_field`` on them.
        
        Args:
          mode_nums: Mode numbers to compute. 
              Examples are [1,2,3,4,5] or [3,1,6,8]. 
              The mode numbers need not be sorted,
              and sorting does not increase efficiency. 
          mode_path:
              Full path to mode location, e.g. /home/user/mode_%d.txt.
              
        Kwargs:
          index_from:
              Index modes starting from 0, 1, or other.
          direct_field_paths:
              Paths to adjoint fields. Optional if already given when calling 
              ``self.compute_decomp``.
            
        self.R_sing_vecs and self.sing_vals must exist, else UndefinedError.
        """
        
        if self.R_sing_vecs is None:
            raise util.UndefinedError('Must define self.R_sing_vecs')
        if self.sing_vals is None:
            raise util.UndefinedError('Must define self.sing_vals')
            
        if direct_field_paths is not None:
            self.direct_field_paths = direct_field_paths
        if self.direct_field_paths is None:
            raise util.UndefinedError('Must specify direct_field_paths')
        # Switch to N.dot...
        build_coeff_mat = N.mat(self.R_sing_vecs)*N.mat(N.diag(self.sing_vals**-0.5))

        self.field_ops._compute_modes(mode_nums, mode_path, 
            self.direct_field_paths, build_coeff_mat, index_from=index_from)
    
    def compute_adjoint_modes(self, mode_nums, mode_path, index_from=1,
        adjoint_field_paths=None):
        """Computes the adjoint modes and calls ``self.put_field`` on them.
        
        Args:
            mode_nums: Mode numbers to compute. 
                Examples are [1,2,3,4,5] or [3,1,6,8]. 
                The mode numbers need not be sorted,
                and sorting does not increase efficiency. 
                
            mode_path:
                Full path to mode location, e.g. /home/user/mode_%d.txt.
        
        Kwargs:
            index_from: Index modes starting from 0, 1, or other.
                
            adjoint_field_paths: Paths to adjoint fields. 
            		Optional if already given when calling ``self.compute_decomp``.
            
        self.L_sing_vecs and self.sing_vals must exist, else UndefinedError.
        """
        
        if self.L_sing_vecs is None:
            raise UndefinedError('Must define self.L_sing_vecs')
        if self.sing_vals is None:
            raise UndefinedError('Must define self.sing_vals')
        if adjoint_field_paths is not None:
            self.adjoint_field_paths=adjoint_field_paths
        if self.adjoint_field_paths is None:
            raise util.UndefinedError('Must specify adjoint_field_paths')

        self.sing_vals = N.squeeze(N.array(self.sing_vals))
        # Switch to N.dot...
        build_coeff_mat = N.mat(self.L_sing_vecs) * \
            N.mat(N.diag(self.sing_vals**-0.5))
                 
        self.field_ops._compute_modes(mode_nums, mode_path,
            self.adjoint_field_paths, build_coeff_mat, index_from=index_from)
    