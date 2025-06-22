"""
Data compression service for logs, experiment data, and general files.
Uses configuration from config.json through config_service.py.
"""
import gzip
import zipfile
import bz2
import lzma
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Callable
from dataclasses import dataclass
from threading import Lock
import os

from src.utils.config_service import get_config_service, ConfigurationError
from src.utils.log_service import debug, info, warning, error
from src.utils.concurrency.thread_pool import get_thread_pool_manager, ThreadPoolType

@dataclass
class CompressionSettings:
    """Configuration for compression operations"""
    enabled: bool = True
    algorithm: str = "gzip"
    level: int = 5
    preserve_original: bool = False


@dataclass
class RotationSettings:
    """Configuration for file rotation"""
    enabled: bool = True
    max_size_mb: int = 100
    max_age_days: int = 7
    max_files: int = 10


class CompressionError(Exception):
    """Raised when compression operations fail"""
    pass


class CompressionService:
    """
    Service for compressing and rotating data files.
    
    Handles three types of data:
    - Logs: Application logs with rotation based on size and age
    - Experiment data: Experiment results and measurements
    - General data: Any other data files that need compression
    
    Uses configuration from config.json through config_service.py to get:
    - Compression algorithm and level
    - File rotation settings
    - Storage paths
    """
    
    # Supported compression algorithms
    COMPRESSION_ALGORITHMS = {
        'gzip': {
            'extension': '.gz',
            'compressor': gzip.compress,
            'decompressor': gzip.decompress,
            'open_func': gzip.open
        },
        'bz2': {
            'extension': '.bz2',
            'compressor': bz2.compress,
            'decompressor': bz2.decompress,
            'open_func': bz2.open
        },
        'lzma': {
            'extension': '.xz',
            'compressor': lzma.compress,
            'decompressor': lzma.decompress,
            'open_func': lzma.open
        },
        'zip': {
            'extension': '.zip',
            'compressor': None,  # Handled separately
            'decompressor': None,  # Handled separately
            'open_func': None
        }
    }
    
    def __init__(self):
        """Initialize compression service with configuration from config service"""
        self._lock = Lock()
        self._config_service = get_config_service()
        if self._config_service is None:
            raise CompressionError("Configuration service not available")
          # Load configuration
        self._load_configuration()
        
        # Ensure output directories exist
        self._create_directories()
        
        info(f"Compression service initialized with algorithm: {self._compression_settings.algorithm}")
    
    def _load_configuration(self) -> None:
        """Load compression and rotation settings from configuration"""
        try:
            if self._config_service is None:
                raise ConfigurationError("Configuration service not available")
               # Load compression settings
            compression_config = self._config_service.get('data_storage.compression', dict, {})
            self._compression_settings = CompressionSettings(
                enabled=compression_config.get('enabled', True),
                algorithm=compression_config.get('algorithm', 'gzip'),
                level=compression_config.get('level', 5),
                preserve_original=compression_config.get('preserve_original', False)
            )
            
            # Load streaming settings
            self._chunk_size = compression_config.get('chunk_size', 1024 * 1024)  # Default 1MB chunks
            
            # Validate compression algorithm
            if self._compression_settings.algorithm not in self.COMPRESSION_ALGORITHMS:
                warning(f"Unsupported compression algorithm: {self._compression_settings.algorithm}. Using gzip.")
                self._compression_settings.algorithm = 'gzip'
            
            # Load rotation settings
            rotation_config = self._config_service.get('data_storage.file_rotation', dict, {})
            self._rotation_settings = RotationSettings(
                enabled=rotation_config.get('enabled', True),
                max_size_mb=rotation_config.get('max_size_mb', 100),
                max_age_days=rotation_config.get('max_age_days', 7),
                max_files=rotation_config.get('max_files', 10)
            )
            
            # Load storage paths under data folder
            storage_paths = self._config_service.get('data_storage.storage_paths', dict, {}) or {}
            base_data_dir = Path(storage_paths.get('base', 'data'))
            self._raw_path = Path(storage_paths.get('raw', str(base_data_dir / 'raw')))
            self._processed_path = Path(storage_paths.get('processed', str(base_data_dir / 'processed')))
            self._cache_path = Path(storage_paths.get('cache', str(base_data_dir / 'cache')))
            # Log directory
            self._log_path = Path(storage_paths.get('logs', str(base_data_dir / 'logs')))
            # Experiment directory base
            exp_cfg = storage_paths.get('experiments', {}) or {}
            self._experiment_path = Path(exp_cfg.get('base', str(base_data_dir / 'experiments')))
         
        except Exception as e:
            error(f"Failed to load compression configuration: {e}")
            # Fallback defaults under data folder
            self._compression_settings = CompressionSettings()
            self._rotation_settings = RotationSettings()
            self._raw_path = Path('data/raw')
            self._processed_path = Path('data/processed')
            self._cache_path = Path('data/cache')
            self._log_path = Path('data/logs')
            self._experiment_path = Path('data/experiments')
    
    def _create_directories(self) -> None:
        """Create necessary directories for compressed files"""
        directories = [
            self._raw_path / 'compressed',
            self._processed_path / 'compressed',
            self._cache_path / 'compressed',
            self._log_path / 'compressed',
            self._experiment_path / 'compressed'
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def compress_file(self, 
                     file_path: Union[str, Path], 
                     output_path: Optional[Union[str, Path]] = None,
                     data_type: str = 'general') -> Optional[Path]:
        """
        Compress a single file using configured compression algorithm.
        
        Args:
            file_path: Path to file to compress
            output_path: Optional output path. If None, creates compressed file next to original
            data_type: Type of data being compressed ('logs', 'experiment', 'general')
            
        Returns:
            Path to compressed file, or None if compression failed
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            error(f"File not found: {file_path}")
            return None
        
        if not self._compression_settings.enabled:
            debug("Compression disabled, skipping")
            return None
        
        try:
            with self._lock:
                # Determine output path
                if output_path is None:
                    compressed_dir = file_path.parent / 'compressed'
                    compressed_dir.mkdir(parents=True, exist_ok=True)
                    
                    algorithm_info = self.COMPRESSION_ALGORITHMS[self._compression_settings.algorithm]
                    extension = algorithm_info['extension']
                    output_path = compressed_dir / f"{file_path.name}{extension}"
                else:
                    output_path = Path(output_path)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Perform compression
                if self._compression_settings.algorithm == 'zip':
                    self._compress_zip(file_path, output_path)
                else:
                    self._compress_standard(file_path, output_path)
                
                # Remove original if not preserving
                if not self._compression_settings.preserve_original:
                    file_path.unlink()
                    debug(f"Removed original file: {file_path}")
                    if file_path.exists():
                        warning(f"Source file was not deleted: {file_path}")
                
                info(f"Compressed {data_type} file: {file_path} -> {output_path}")
                return output_path
                
        except (OSError, zipfile.BadZipFile, lzma.LZMAError) as e:
            error(f"Failed to compress file {file_path}: {e}")
            return None
        except Exception as e:
            error(f"Unexpected error compressing file {file_path}: {e}")
            raise
    def _compress_standard(self, input_path: Path, output_path: Path) -> None:
        """Compress file using gzip, bz2, or lzma with chunk-based streaming"""
        algorithm_info = self.COMPRESSION_ALGORITHMS[self._compression_settings.algorithm]
        open_func = algorithm_info['open_func']

        # Prepare compression parameters based on algorithm
        if self._compression_settings.algorithm == 'gzip':
            open_kwargs = {'compresslevel': self._compression_settings.level}
        elif self._compression_settings.algorithm == 'bz2':
            open_kwargs = {'compresslevel': self._compression_settings.level}
        else:  # lzma
            open_kwargs = {'preset': self._compression_settings.level}

        # Stream compress the file in chunks to reduce memory usage
        with open(input_path, 'rb') as src_file:
            with open_func(output_path, 'wb', **open_kwargs) as dest_file:
                while True:
                    chunk = src_file.read(self._chunk_size)
                    if not chunk:
                        break
                    dest_file.write(chunk)
    
    def _compress_zip(self, input_path: Path, output_path: Path) -> None:
        """Compress file using ZIP format"""
        compression_level = zipfile.ZIP_DEFLATED
        
        with zipfile.ZipFile(output_path, 'w', compression_level, compresslevel=self._compression_settings.level) as zf:
            zf.write(input_path, input_path.name)
    
    def compress_directory(self, 
                          directory_path: Union[str, Path],
                          pattern: str = "*",
                          data_type: str = 'general',
                          recursive: bool = True) -> List[Path]:
        """
        Compress all files in a directory matching a pattern.
        
        Args:
            directory_path: Directory to scan for files
            pattern: File pattern to match (e.g., "*.log", "*.csv")
            data_type: Type of data being compressed
            recursive: Whether to search subdirectories
            
        Returns:
            List of compressed file paths
        """
        directory_path = Path(directory_path)
        
        if not directory_path.exists():
            error(f"Directory not found: {directory_path}")
            return []
        
        compressed_files: List[Path] = []
        # Discover files
        files = directory_path.rglob(pattern) if recursive else directory_path.glob(pattern)
        # Parallelize compression on FILE_IO pool
        pool = get_thread_pool_manager().get_pool(ThreadPoolType.FILE_IO)
        futures = []
        for file_path in files:
            if file_path.is_file() and not self._is_already_compressed(file_path):
                futures.append(pool.submit_task(lambda p=file_path: self.compress_file(p, None, data_type)))
        # Collect results
        for fut in futures:
            try:
                result = fut.result()
                if result:
                    compressed_files.append(result)
            except (OSError, CompressionError) as e:
                error(f"Error compressing file in pool: {e}")
            except Exception as e:
                error(f"Unexpected error compressing file in pool: {e}")
                raise
        info(f"Compressed {len(compressed_files)} {data_type} files in {directory_path}")
        return compressed_files
    
    def _is_already_compressed(self, file_path: Path) -> bool:
        """Check if file is already compressed"""
        compressed_extensions = {
            info["extension"] for info in self.COMPRESSION_ALGORITHMS.values()
        }
        return file_path.suffix in compressed_extensions or "compressed" in file_path.parts
    
    def rotate_logs(self) -> None:
        """Rotate log files based on configuration"""
        if not self._rotation_settings.enabled:
            debug("Log rotation disabled")
            return
        
        try:
            log_files = list(self._log_path.glob("*.log"))
            
            for log_file in log_files:
                self._rotate_file_if_needed(log_file, 'logs')
            
            # Clean up old compressed log files
            self._cleanup_old_files(self._log_path / 'compressed', 'logs')
            
        except Exception as e:
            error(f"Failed to rotate logs: {e}")
    
    def rotate_experiment_data(self) -> None:
        """Rotate experiment data files based on configuration"""
        if not self._rotation_settings.enabled:
            debug("Experiment data rotation disabled")
            return
        
        try:
            # Rotate CSV and other data files
            for pattern in ["*.csv", "*.json", "*.txt"]:
                data_files = list(self._experiment_path.rglob(pattern))
                
                for data_file in data_files:
                    self._rotate_file_if_needed(data_file, 'experiment')
            
            # Clean up old compressed experiment files
            self._cleanup_old_files(self._experiment_path / 'compressed', 'experiment')
            
        except Exception as e:
            error(f"Failed to rotate experiment data: {e}")
    
    def rotate_general_data(self, data_paths: Optional[List[Union[str, Path]]] = None) -> None:
        """
        Rotate general data files based on configuration.
        
        Args:
            data_paths: Optional list of specific paths to check. If None, uses configured paths.
        """
        if not self._rotation_settings.enabled:
            debug("General data rotation disabled")
            return
        
        try:
            if data_paths is None:
                data_paths = [self._raw_path, self._processed_path, self._cache_path]
            
            for data_path in data_paths:
                data_path = Path(data_path)
                if not data_path.exists():
                    continue
                
                # Rotate various file types
                for pattern in ["*.csv", "*.json", "*.txt", "*.dat"]:
                    data_files = list(data_path.rglob(pattern))
                    
                    for data_file in data_files:
                        if not self._is_already_compressed(data_file):
                            self._rotate_file_if_needed(data_file, 'general')
                
                # Clean up old compressed files
                compressed_dir = data_path / 'compressed'
                if compressed_dir.exists():
                    self._cleanup_old_files(compressed_dir, 'general')
            
        except Exception as e:
            error(f"Failed to rotate general data: {e}")
    
    def _rotate_file_if_needed(self, file_path: Path, data_type: str) -> None:
        """Rotate file if it meets rotation criteria"""
        try:
            # Check file size
            if file_path.stat().st_size > self._rotation_settings.max_size_mb * 1024 * 1024:
                info(f"Rotating {data_type} file due to size: {file_path}")
                self.compress_file(file_path, data_type=data_type)
                return
            
            # Check file age
            file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_age.days > self._rotation_settings.max_age_days:
                info(f"Rotating {data_type} file due to age: {file_path}")
                self.compress_file(file_path, data_type=data_type)
                return
                
        except Exception as e:
            error(f"Failed to check rotation criteria for {file_path}: {e}")
    
    def _cleanup_old_files(self, compressed_dir: Path, data_type: str) -> None:
        """Remove old compressed files beyond max_files limit"""
        try:
            if not compressed_dir.exists():
                return
            
            # Get all compressed files sorted by modification time (newest first)
            compressed_files = []
            for ext in ['.gz', '.bz2', '.xz', '.zip']:
                compressed_files.extend(compressed_dir.glob(f"*{ext}"))
            
            compressed_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Remove files beyond the limit
            files_to_remove = compressed_files[self._rotation_settings.max_files:]
            
            for file_path in files_to_remove:
                file_path.unlink()
                info(f"Removed old {data_type} compressed file: {file_path}")
                
        except Exception as e:
            error(f"Failed to cleanup old compressed files: {e}")
    
    def decompress_file(self, compressed_path: Union[str, Path], output_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
        """
        Decompress a compressed file.
        
        Args:
            compressed_path: Path to compressed file
            output_path: Optional output path. If None, creates file next to compressed file
            
        Returns:
            Path to decompressed file, or None if decompression failed
        """
        compressed_path = Path(compressed_path)
        
        if not compressed_path.exists():
            error(f"Compressed file not found: {compressed_path}")
            return None
        
        try:
            # Determine compression type from extension
            algorithm = None
            for alg, alg_info in self.COMPRESSION_ALGORITHMS.items():
                if compressed_path.suffix == alg_info['extension']:
                    algorithm = alg
                    break
            
            if algorithm is None:
                error(f"Unknown compression format: {compressed_path.suffix}")
                return None
            
            # Determine output path
            if output_path is None:
                # Remove compression extension to get original filename
                output_path = compressed_path.with_suffix('')
                if output_path.suffix == compressed_path.stem.split('.')[-1]:
                    # Handle cases like file.txt.gz -> file.txt
                    original_name = compressed_path.name
                    for ext in ['.gz', '.bz2', '.xz', '.zip']:
                        if original_name.endswith(ext):
                            original_name = original_name[:-len(ext)]
                            break
                    output_path = compressed_path.parent / original_name
            else:
                output_path = Path(output_path)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Perform decompression
            if algorithm == 'zip':
                self._decompress_zip(compressed_path, output_path)
            else:
                self._decompress_standard(compressed_path, output_path, algorithm)
            
            info(f"Decompressed file: {compressed_path} -> {output_path}") 
            return output_path
            
        except Exception as e:
            error(f"Failed to decompress file {compressed_path}: {e}")
            return None
    
    def _decompress_standard(self, compressed_path: Path, output_path: Path, algorithm: str) -> None:
        """Decompress file using gzip, bz2, or lzma with streaming to handle large files efficiently"""
        algorithm_info = self.COMPRESSION_ALGORITHMS[algorithm]
        open_func = algorithm_info['open_func']

        # Stream decompression in chunks to minimize memory usage
        with open_func(compressed_path, 'rb') as src_file:
            with open(output_path, 'wb') as dest_file:
                while True:
                    chunk = src_file.read(self._chunk_size)
                    if not chunk:
                        break
                    dest_file.write(chunk)
    
    def _decompress_zip(self, compressed_path: Path, output_path: Path) -> None:
        """Decompress ZIP file"""
        with zipfile.ZipFile(compressed_path, 'r') as zf:
            # If output_path is a directory, extract all files
            if output_path.is_dir():
                zf.extractall(output_path)
            else:
                # Extract first file to specified path
                names = zf.namelist()
                if names:
                    with zf.open(names[0]) as source, open(output_path, 'wb') as target:
                        shutil.copyfileobj(source, target)
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """Get statistics about compressed files"""
        stats = {
            'compression_enabled': self._compression_settings.enabled,
            'algorithm': self._compression_settings.algorithm,
            'compression_level': self._compression_settings.level,
            'rotation_enabled': self._rotation_settings.enabled,
            'max_size_mb': self._rotation_settings.max_size_mb,
            'max_age_days': self._rotation_settings.max_age_days,
            'compressed_files': {}
        }
        
        # Count compressed files in each directory
        directories = {
            'logs': self._log_path / 'compressed',
            'experiments': self._experiment_path / 'compressed',
            'raw': self._raw_path / 'compressed',
            'processed': self._processed_path / 'compressed',
            'cache': self._cache_path / 'compressed'
        }
        
        for name, directory in directories.items():
            if directory.exists():
                compressed_files = []
                for ext in ['.gz', '.bz2', '.xz', '.zip']:
                    compressed_files.extend(directory.glob(f"*{ext}"))
                
                total_size = sum(f.stat().st_size for f in compressed_files)
                stats['compressed_files'][name] = {
                    'count': len(compressed_files),
                    'total_size_mb': round(total_size / (1024 * 1024), 2)
                }
        
        return stats
    
    def perform_maintenance(self) -> None:
        """Perform routine maintenance: rotation and cleanup"""
        info("Starting compression service maintenance")
        
        try:
            # Rotate files
            self.rotate_logs()
            self.rotate_experiment_data()
            self.rotate_general_data()
            
            info("Compression service maintenance completed")
            
        except Exception as e:
            error(f"Error during compression service maintenance: {e}")
    
    def reload_configuration(self) -> None:
        """Reload configuration from config service"""
        info("Reloading compression service configuration")
        self._load_configuration()
        self._create_directories()


# Global compression service instance
_compression_service_instance: Optional[CompressionService] = None


def get_compression_service() -> Optional[CompressionService]:
    """Get the global compression service instance"""
    global _compression_service_instance
    if _compression_service_instance is None:
        try:
            _compression_service_instance = CompressionService()
        except Exception as e:
            error(f"Failed to create compression service: {e}")
            return None
    return _compression_service_instance


def set_compression_service(service: CompressionService) -> None:
    """Set the global compression service instance"""
    global _compression_service_instance
    _compression_service_instance = service
